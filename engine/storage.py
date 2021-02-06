import json
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import fields as dataclass_fields
from enum import Enum
from pathlib import Path
from sqlite3 import Connection, Row, connect
from typing import Any, ContextManager, Dict, Generic, List, Optional, Sequence, Tuple, Type, TypeVar, Union

from picaro.common.serializer import deserialize, recursive_from_dict, serialize


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
        if store_cls in cls.INITIALIZED_STORES:
            return

        for sub_cls in store_cls.SUBTABLES.values():
            sub_cls.PARENT_STORE = store_cls

        if cls.FIRST:
            store_cls.initialize(active_conn)

        cls.INITIALIZED_STORES.add(store_cls)


T = TypeVar("T")


class StorageBase(ABC, Generic[T]):
    TABLE_NAME = "unset"
    TYPE: Type[T]
    PARENT_STORE: Optional["StorageBase[Any]"] = None
    SUBTABLES = {}

    @classmethod
    @abstractmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        # list of (name, type, is_primary) columns
        ...

    @classmethod
    @abstractmethod
    def _construct_val(cls, row: Dict[str, Any]) -> T:
        # construct a single T object based on the given row (subtables
        # will be already rehydrated in the dict)
        ...

    @classmethod
    @abstractmethod
    def _project_val(cls, val: T) -> Dict[str, Any]:
        # convert a single T object into a row (subtables
        # should be left unconverted in the dict)
        ...

    @classmethod
    def _initial_data(cls) -> List[T]:
        json_path = ConnectionWrapper.JSON_PATH / f"{cls.TABLE_NAME}s.json"
        if not json_path.exists():
            return []
        with open(json_path) as f:
            return deserialize(f.read(), List[cls.TYPE])

    @classmethod
    def initialize(cls, active_conn: Optional[Connection]) -> None:
        with ConnectionWrapper.connect(active_conn) as conn:
            cls._create_table_helper(active_conn=conn)
            for sub_base in cls.SUBTABLES.values():
                sub_base._create_table_helper(conn)
            initial_vals = cls._initial_data()
            if initial_vals:
                cls._insert_helper(initial_vals, conn)

    @classmethod
    def _create_table_helper(cls, active_conn: Optional[Connection]) -> None:
        cols = cls._full_table_schema()
        pks = ", ".join(c[0] for c in cols if c[2])
        cols.append(f"primary key ({pks})")
        sql = f"CREATE TABLE {cls.TABLE_NAME} (\n  "
        sql += ",\n  ".join(f"{c[0]} {c[1]}" for c in cols)
        sql += "\n)"
        with ConnectionWrapper.connect(active_conn) as conn:
            conn.execute(sql, {})

    @classmethod
    def _full_table_schema(cls) -> List[Tuple[str, str, bool]]:
        cols = cls._table_schema()
        if cls.PARENT_STORE:
            par_cols = [c for c in cls.PARENT_STORE._table_schema() if c[2]]
            for c in par_cols:
                c[0] = cls.PARENT_STORE.TABLE_NAME + "_" + c[0]
            cols = par_cols + cols
        return cols

    @classmethod
    def _select_helper(cls, where_clauses: List[str], params: Dict[str, Any], active_conn: Optional[Connection]) -> List[T]:
        return cls._select_helper_grouped(where_clauses, params, active_conn)[()]

    @classmethod
    def _select_helper_grouped(cls, where_clauses: List[str], params: Dict[str, Any], active_conn: Optional[Connection]) -> Dict[Sequence[Any], List[T]]:
        sql = f"SELECT * FROM {cls.TABLE_NAME}"
        if where_clauses:
            sql += " WHERE (" + ") AND (".join(where_clauses) + ")"

        ret = defaultdict(list)
        with ConnectionWrapper.connect(active_conn) as conn:
            if not active_conn:
                ConnectionWrapper.initialize_store(cls, conn)
            rows = list(conn.execute(sql, params))
            all_secondaries = cls._select_secondaries(rows, conn)
            for row, snds in zip(rows, all_secondaries):
                for sf, sv in snds.items():
                    row[sf] = sv
                val = cls._construct_val(row)
                parent_key = cls._select_parent_key(row)
                ret[parent_key].append(val)
            return ret

    @classmethod
    def _select_parent_key(cls, row: Dict[str, Any]) -> Sequence[Any]:
        if not cls.PARENT_STORE:
            return ()
        par = cls.PARENT_STORE
        return tuple(row[par.TABLE_NAME + "_" + c[0]] for c in par._table_schema() if c[2])

    @classmethod
    def _select_secondaries(cls, rows: List[Dict[str, Any]], conn: Connection) -> List[Dict[str, List[Any]]]:
        ret = [defaultdict(list) for _ in rows]
        if not cls.SUBTABLES:
            return ret

        pk_names = [c for c in cls._table_schema() if c[2]]
        pk_values = [[row[n] for n in pk_names] for row in rows]
        select_wheres = " OR ".join(["((" + ") AND (".join(f"{cls.TABLE_NAME}_{n} = ?" for n in pk_names) + "))"] * len(rows))
        select_params = [v for row in pk_values for val in row]
        row_idxs = {tuple(vals): idx for idx, vals in enumerate(pk_values)}

        ret = [defaultdict(list) for _ in rows]
        for sub_field, sub_base in cls.SUBTABLES.items():
            grps = sub_base._select_helper(select_wheres, select_params, conn)
            for key, sub_vals in grps.items():
                ret[row_idxs[key]][sub_field].extend(sub_vals)
        return ret

    @classmethod
    def _insert_helper(cls, values: List[T], active_conn: Optional[Connection]) -> None:
        all_projected = cls._project_all(values)
        with ConnectionWrapper.connect(active_conn) as conn:
            if not active_conn:
                ConnectionWrapper.initialize_store(cls, conn)
            for storage_base, rows in all_projected.items():
                names = list(rows[0].keys())
                each_params = tuple(row[n] for row in rows for n in names)
                values_clause = "(" + ", ".join("?" for _ in names) + ")"
                sql = f"INSERT INTO {storage_base.TABLE_NAME} ("
                sql += ", ".join(n for n in names)
                sql += ") VALUES " + ", ".join(values_clause for _ in rows)
                conn.execute(sql, each_params)

    @classmethod
    def _project_all(cls, values: List[T]) -> Dict["StorageBase[Any]", List[Dict[str, Any]]]:
        all_projected = defaultdict(list)
        for val in values:
            proj = cls._project_val(val)
            all_projected[cls].append(proj)
            pk_vals = {cls.TABLE_NAME + "_" + c[0]: proj[c[0]] for c in cls._table_schema() if c[2]}
            for sub_f, sub_cls in cls.SUBTABLES.items():
                sub_projection = sub_cls._project_all(val[sub_f])
                # add the parent row's pk data to the sub's fields
                for sub_val in sub_projection[sub_cls]:
                    sub_val.update(pk_vals)
                for ss_cls, ss_rows in sub_projection.items():
                    all_projected[ss_cls].extend(ss_rows)
        return all_projected


class ValueStorageBase(StorageBase[str]):
    TYPE: Type[T] = str

    @classmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        return [("value", "text not null", True)]

    @classmethod
    def _construct_val(cls, row: Dict[str, Any]) -> str:
        return row["value"]

    @classmethod
    def _project_val(cls, val: str) -> Dict[str, Any]:
        return {"value": val}


class ObjectStorageBase(StorageBase[T]):
    TYPE: Type[T]
    PRIMARY_KEY: str

    @classmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        cols = []
        for field_info in dataclass_fields(cls.TYPE):
            fname = field_info.name
            ftype = field_info.type
            if fname in cls.SUBTABLES:
                continue
            col_name = fname
            base_type = getattr(ftype, "__origin__", ftype)
            nn = " not null"
            if base_type == Union: # ie, it was an optional
                # pull out the first type which is assumed to be the non-none type
                ftype = ftype.__args__[0]
                base_type = getattr(ftype, "__origin__", ftype)
                nn = " null"
            if base_type == int:
                col_type = "integer" + nn
            else:
                col_type = "text" + nn

            cols.append((col_name, col_type, col_name == cls.PRIMARY_KEY))

        return cols

    @classmethod
    def _construct_val(cls, row: Dict[str, Any]) -> T:
        return recursive_from_dict(row, cls.TYPE)

    @classmethod
    def _project_val(cls, val: T) -> Dict[str, Any]:
        ret = {}
        for field_info in dataclass_fields(cls.TYPE):
            fname = field_info.name
            ftype = field_info.type
            fval = getattr(val, fname)
            if fname in cls.SUBTABLES:
                ret[fname] = fval
            else:
                ret[fname] = cls._serialize_val(ftype, fval)
        return ret

    @classmethod
    def _serialize_val(cls, ftype: Type[T], fval: Any) -> Any:
        bt = getattr(ftype, "__origin__", ftype)
        if bt in (str, int, float, bool):
            return fval
        elif issubclass(bt, Enum):
            return fval.name
        else:
            return serialize(fval)

    @classmethod
    def _update_helper(cls, updates: Dict[str, Any], where_clauses: List[str], params: Dict[str, Any], active_conn: Optional[Connection]) -> None:
        all_params = {k: v for k, v in params.items()}
        sql = f"UPDATE {cls.TABLE_NAME} SET "
        update_clauses = []
        ftypes = {f.name: f.type for f in dataclass_fields(cls.TYPE)}
        for uk, uv in updates.items():
            if uk in cls.SUBTABLES:
                raise Exception("Update doesn't handle subtables yet")
            update_clauses.append(f"{uk} = :{uk}")
            all_params[uk] = cls._serialize_val(uk, ftypes[uk], uv)
        sql += ", ".join(update_clauses)
        sql += " WHERE (" + ") AND (".join(where_clauses) + ")"

        with ConnectionWrapper.connect(active_conn) as conn:
            if not active_conn:
                ConnectionWrapper.initialize_store(cls, conn)
            conn.execute(sql, all_params)
