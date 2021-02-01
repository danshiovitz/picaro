import json
from abc import ABC, abstractmethod
from contextlib import nullcontext
from enum import Enum
from pathlib import Path
from sqlite3 import Connection, Row, connect
from typing import Any, ContextManager, Dict, Generic, List, Optional, Type, TypeVar, Union

from picaro.common.serializer import recursive_from_dict, serialize


class ConnectionWrapper:
    DB_STR: str = "UNSET"
    JSON_PATH: str = "UNSET"
    FIRST: bool = False
    INITIALIZED_STORES = set()
    MEMORY_CONNECTION_HANDLE: Optional[Connection] = None

    @classmethod
    def initialize(cls, db_path: Optional[str], json_path: str) -> None:
        if db_path:
            cls.DB_STR = f"file:{db_path}"
            cls.FIRST = Path.exists(db_path)
        else:
            cls.DB_STR = "file:ephemeral_db?mode=memory&cache=shared"
            cls.FIRST = True
            # actually go ahead and open a connection to this shared memory
            # so it'll stick around for the program
            cls.MEMORY_CONNECTION_HANDLE = cls.connect(None)
        cls.JSON_PATH = json_path

    @classmethod
    def connect(cls, active_conn: Optional[Connection]) -> ContextManager[Connection]:
        if active_conn:
            return nullcontext(enter_result=active_conn)
        else:
            connection = connect(cls.DB_STR, uri=True)
            connection.row_factory = Row
            return connection

    @classmethod
    def initialize_store(cls, store_cls: Type[Any], active_conn: Optional[Connection]) -> None:
        if not cls.FIRST or store_cls in cls.INITIALIZED_STORES:
            return
        store_cls.initialize(active_conn)
        cls.INITIALIZED_STORES.add(store_cls)


T = TypeVar("T")


class StorageBase(ABC, Generic[T]):
    TABLE_NAME = "unset"

    @classmethod
    @abstractmethod
    def to_type(cls, row: Dict[str, Any]) -> T:
        ...

    @classmethod
    @abstractmethod
    def table_schema(cls) -> str:
        ...

    @classmethod
    def initial_data(cls) -> List[Dict[str, Any]]:
        return []

    @classmethod
    def initialize(cls, active_conn: Optional[Connection]) -> None:
        with ConnectionWrapper.connect(active_conn) as conn:
            conn.execute(cls.table_schema())
            initial_vals = cls.initial_data()
            if initial_vals:
                cls._insert_helper(initial_vals, conn)

    @classmethod
    def _select_helper(cls, where_clauses: List[str], params: Dict[str, Any], active_conn: Optional[Connection]) -> List[T]:
        sql = f"SELECT * FROM {cls.TABLE_NAME}"
        if where_clauses:
            sql += " WHERE (" + ") AND (".join(where_clauses) + ")"

        with ConnectionWrapper.connect(active_conn) as conn:
            if not active_conn:
                ConnectionWrapper.initialize_store(cls, conn)
            return [cls.to_type(row) for row in conn.execute(sql, params)]

    @classmethod
    def _insert_helper(cls, values: List[Dict[str, Any]], active_conn: Optional[Connection]) -> None:
        names = list(values[0].keys())
        each_params = tuple(val[n] for val in values for n in names)
        values_clause = "(" + ", ".join("?" for _ in names) + ")"
        sql = f"INSERT INTO {cls.TABLE_NAME} ("
        sql += ", ".join(n for n in names)
        sql += ") VALUES " + ", ".join(values_clause for _ in values)
        with ConnectionWrapper.connect(active_conn) as conn:
            if not active_conn:
                ConnectionWrapper.initialize_store(cls, conn)
            conn.execute(sql, each_params)

    @classmethod
    def _load_json_helper(cls) -> Any:
        with open(ConnectionWrapper.JSON_PATH / f"{cls.TABLE_NAME}s.json") as f:
            return json.loads(f.read())


class ValueStorageBase(StorageBase[str]):
    @classmethod
    def to_type(cls, row: Dict[str, Any]) -> str:
        return row["value"]

    @classmethod
    def table_schema(cls) -> str:
        return f"""
CREATE TABLE {cls.TABLE_NAME} (
    value text not null primary key
)
"""

    @classmethod
    def initial_data(cls) -> List[Dict[str, Any]]:
        json_deser = cls._load_json_helper()
        return [{"value": v} for v in json_deser]


class ObjectStorageBase(StorageBase[T]):
    TYPE: Type[T]
    PRIMARY_KEY: str
    PARENT_TABLE: Optional[StorageBase[Any]] = None
    SUBTABLES = {}

    @classmethod
    def to_type(cls, row: Dict[str, Any]) -> T:
        return recursive_from_dict(row, cls.TYPE)

    @classmethod
    def table_schema(cls) -> str:
        cols = []
        parent_pk_name: Optional[str] = None
        if cls.PARENT_TABLE:
            parent_col = cls.PARENT_TABLE.TABLE_NAME
            parent_col += "_" + cls.PARENT_TABLE.PRIMARY_KEY
            parent_pk_name = parent_col
            parent_col += " "
            parent_col += cls.PARENT_TABLE._column_type(cls.PARENT_TABLE.PRIMARY_KEY)
            cols.append(parent_col)
        for fname, ftype in cls.TYPE._field_types.items():
            if fname in cls.SUBTABLES:
                continue
            col = fname + " " + cls._column_type(fname)
            cols.append(col)
        if cls.PARENT_TABLE:
            cols.append(f"primary key ({parent_pk_name}, {cls.PRIMARY_KEY})")
        else:
            cols.append(f"primary key ({cls.PRIMARY_KEY})")

        sql = f"CREATE TABLE {cls.TABLE_NAME} (\n  "
        sql += ",\n  ".join(cols)
        sql += "\n)"

        sqls = [sql]
        for sub_base in cls.SUBTABLES.values():
            sqls.append(sub_base.table_schema())
        return "; ".join(sqls)

    @classmethod
    def _column_type(cls, field_name) -> str:
        field_type = cls.TYPE._field_types[field_name]
        base_type = getattr(field_type, "__origin__", field_type)
        nn = " not null"
        if base_type == Union: # ie, it was an optional
            # pull out the first type which is assumed to be the non-none type
            field_type = field_type.__args__[0]
            base_type = getattr(field_type, "__origin__", field_type)
            nn = " null"
        if base_type == int:
            return "integer" + nn
        else:
            return "text" + nn

    @classmethod
    def initial_data(cls) -> List[Dict[str, Any]]:
        json_deser = cls._load_json_helper()
        cls._cvt_json_to_row(json_deser)
        return json_deser

    @classmethod
    def _cvt_json_to_row(cls, values: List[Dict[str, Any]]) -> None:
        for js in values:
            for fname, ftype in cls.TYPE._field_types.items():
                bt = getattr(ftype, "__origin__", ftype)
                if bt in (str, int, float, bool) or issubclass(bt, Enum):
                    pass
                elif fname in cls.SUBTABLES:
                    cls.SUBTABLES[fname]._cvt_json_to_row(js[fname])
                else:
                    js[fname] = serialize(js[fname])

    @classmethod
    def initialize(cls, active_conn: Optional[Connection]) -> None:
        for sub_cls in cls.SUBTABLES.values():
            sub_cls.PARENT_TABLE = cls
        super().initialize(active_conn)

    @classmethod
    def _insert_helper(cls, values: List[Dict[str, Any]], active_conn: Optional[Connection]) -> None:
        subdata = {sc: [] for sc in cls.SUBTABLES.values()}
        for sub_f, sub_cls in cls.SUBTABLES.items():
            parent_name = cls.TABLE_NAME + "_" + cls.PRIMARY_KEY
            for val in values:
                parent_value = val[cls.PRIMARY_KEY]
                sub_values = val.remove(sub_f)
                for sv in sub_values:
                    sv[parent_name] = parent_value
                subdata[sub_cls].extend(sub_values)

        with ConnectionWrapper.connect(active_conn) as conn:
            super()._insert_helper(values, conn)
            for sub_cls, sub_values in subdata.items():
                sub_cls._insert_helper(sub_values, conn)
