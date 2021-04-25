import functools
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, fields as dataclass_fields
from enum import Enum
from pathlib import Path
from sqlite3 import Connection, Row, connect
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from picaro.common.serializer import deserialize, recursive_from_dict, serialize


@dataclass
class Session:
    player_id: Optional[int]
    game_id: Optional[int]
    connection: Connection


current_session: ContextVar[Session] = ContextVar("current_session")


class ConnectionManager:
    DB_STR: str = "UNSET"
    FIRST: bool = False
    ALL_STORES: Set[Type["StorageBase[Any]"]] = set()
    MEMORY_CONNECTION_HANDLE: Optional[Connection] = None

    @classmethod
    def initialize(cls, db_path: Optional[str]) -> None:
        if db_path:
            cls.DB_STR = f"file:{db_path}"
            cls.FIRST = Path(db_path).exists()
        else:
            cls.DB_STR = "file:ephemeral_db?mode=memory&cache=shared"
            cls.FIRST = True
            # actually go ahead and open a connection to this shared memory
            # so it'll stick around for the program
            cls.MEMORY_CONNECTION_HANDLE = connect(cls.DB_STR, uri=True)

        with ConnectionManager(player_id=None, game_id=None):
            for store_cls in cls.ALL_STORES:
                store_cls.initialize()

    def __init__(self, player_id: Optional[int], game_id: Optional[int]) -> None:
        if self.DB_STR == "UNSET":
            raise Exception("ConnectionManager not initialized")

        self.player_id = player_id
        self.game_id = game_id

    def __enter__(self) -> "ConnectionManager":
        connection = connect(self.DB_STR, uri=True)
        connection.row_factory = Row
        connection.__enter__()  # type: ignore
        session = Session(
            player_id=self.player_id, game_id=self.game_id, connection=connection
        )
        self.ctx_token = current_session.set(session)
        return self

    def __exit__(self, *exc: Any) -> None:
        session = current_session.get()
        current_session.reset(self.ctx_token)
        session.connection.__exit__(*exc)  # type: ignore

    @classmethod
    def fix_game_id(cls, game_id: int) -> None:
        session = current_session.get()
        session.game_id = game_id


def with_connection() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            game_id = kwargs.get("game_id", None)
            player_id = kwargs.get("player_id", None)
            with ConnectionManager(game_id=game_id, player_id=player_id):
                return func(*args, **kwargs)

        return wrapper

    return decorator


T = TypeVar("T")


class StorageBase(ABC, Generic[T]):
    TABLE_NAME = "unset"
    PARENT_STORE: Optional[Type["StorageBase[Any]"]] = None
    SUBTABLES: Dict[str, Type["StorageBase[Any]"]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore
        if cls.TABLE_NAME != "unset":
            ConnectionManager.ALL_STORES.add(cls)

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
    def initialize(cls) -> None:
        for sub_cls in cls.SUBTABLES.values():
            sub_cls.PARENT_STORE = cls

        cls._create_table_helper()
        for sub_base in cls.SUBTABLES.values():
            sub_base._create_table_helper()

    @classmethod
    def insert_initial_data(cls, json_dir: Path) -> None:
        json_path = json_dir / f"{cls.TABLE_NAME}s.json"
        if not json_path.exists():
            return
        with open(json_path) as f:
            val_type = cls._get_val_type()
            vals: List[T] = deserialize(f.read(), List[val_type])  # type: ignore
        if vals:
            cls._insert_helper(vals)

    @classmethod
    def _create_table_helper(cls) -> None:
        cols = cls._full_table_schema()
        sql = f"CREATE TABLE {cls.TABLE_NAME} (\n  "
        sql += ",\n  ".join(f"{c[0]} {c[1]}" for c in cols)
        pks = ", ".join(c[0] for c in cols if c[2])
        sql += f",\n  primary key ({pks})"
        sql += "\n)"
        current_session.get().connection.execute(sql, {})

    @classmethod
    def _full_table_schema(cls) -> List[Tuple[str, str, bool]]:
        cols = cls._table_schema()
        if cls.PARENT_STORE:
            par_cols = [
                (cls.PARENT_STORE.TABLE_NAME + "_" + c[0], c[1], c[2])
                for c in cls.PARENT_STORE._table_schema()
                if c[2]
            ]
            cols = par_cols + cols
        elif cls.TABLE_NAME != "game":
            cols = [("game_id", "int not null", True)] + cols
        return cols

    @classmethod
    def _select_helper(
        cls, where_clauses: List[str], params: Dict[str, Any]
    ) -> List[T]:
        return cast(List[T], cls._select_helper_grouped(where_clauses, params)[()])

    @classmethod
    def _select_helper_grouped(
        cls, where_clauses: List[str], params: Dict[str, Any]
    ) -> Dict[Sequence[Any], List[T]]:
        session = current_session.get()
        if session.game_id is not None and cls.TABLE_NAME != "game":
            where_clauses.append("game_id = :game_id")
            params["game_id"] = session.game_id
        sql = f"SELECT * FROM {cls.TABLE_NAME}"
        if where_clauses:
            sql += " WHERE (" + ") AND (".join(where_clauses) + ")"
        ret: Dict[Sequence[Any], List[T]] = defaultdict(list)
        rows = list(session.connection.execute(sql, params))
        all_secondaries = cls._select_secondaries(rows)
        for row, snds in zip(rows, all_secondaries):
            for sf, sv in snds.items():
                row[sf] = sv
            val: T = cls._construct_val(row)
            parent_key = cls._select_parent_key(row)
            ret[parent_key].append(val)
        return ret

    @classmethod
    def _select_parent_key(cls, row: Dict[str, Any]) -> Sequence[Any]:
        if not cls.PARENT_STORE:
            return ()
        par = cls.PARENT_STORE
        return tuple(
            row[par.TABLE_NAME + "_" + c[0]] for c in par._table_schema() if c[2]
        )

    @classmethod
    def _select_secondaries(
        cls, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, List[Any]]]:
        ret: List[Dict[str, List[Any]]] = [defaultdict(list) for _ in rows]
        if not cls.SUBTABLES:
            return ret

        pk_names = [c[0] for c in cls._table_schema() if c[2]]
        select_wheres = " OR ".join(
            "(("
            + ") AND (".join(
                f"{cls.TABLE_NAME}_{n} = :{cls.TABLE_NAME}_{n}_{ridx}" for n in pk_names
            )
            + "))"
            for ridx in range(len(rows))
        )
        select_params = {
            f"{cls.TABLE_NAME}_{n}_{ridx}": rows[ridx][n]
            for ridx in range(len(rows))
            for n in pk_names
        }
        row_idxs: Dict[Sequence[Any], int] = {
            tuple(row[n] for n in pk_names): idx for idx, row in enumerate(rows)
        }

        ret = [defaultdict(list) for _ in rows]
        for sub_field, sub_base in cls.SUBTABLES.items():
            grps: Dict[Sequence[Any], List[Any]] = sub_base._select_helper_grouped(
                [select_wheres], select_params
            )
            for key, sub_vals in grps.items():
                ret[row_idxs[key]][sub_field].extend(sub_vals)
        return ret

    @classmethod
    def _insert_helper(cls, values: List[T]) -> int:
        # can get issues with max param count in sqlite when inserting
        # too many fields at once, so chunk it:
        last_id = -1
        for idx in range(0, len(values), 20):
            all_projected = cls._project_all(values[idx : idx + 20])
            for storage_base, rows in all_projected.items():
                names = list(n for n in rows[0].keys() if n != "id")
                each_params = tuple(row[n] for row in rows for n in names)
                values_clause = "(" + ", ".join("?" for _ in names) + ")"
                sql = f"INSERT INTO {storage_base.TABLE_NAME} ("
                sql += ", ".join(n for n in names)
                sql += ") VALUES " + ", ".join(values_clause for _ in rows)
                current_session.get().connection.execute(sql, each_params)
                if storage_base == cls:
                    sql = "SELECT last_insert_rowid() AS last_id"
                    row = current_session.get().connection.execute(sql, ()).fetchone()
                    last_id = row["last_id"]
        return last_id

    @classmethod
    def _project_all(
        cls, values: List[T]
    ) -> Dict[Type["StorageBase[Any]"], List[Dict[str, Any]]]:
        session = current_session.get()

        all_projected: Dict[
            Type["StorageBase[Any]"], List[Dict[str, Any]]
        ] = defaultdict(list)
        for val in values:
            proj = cls._project_val(val)
            if (
                session.game_id is not None
                and cls.PARENT_STORE is None
                and cls.TABLE_NAME != "game"
            ):
                proj["game_id"] = session.game_id
            all_projected[cls].append(proj)
            pk_vals = {
                cls.TABLE_NAME + "_" + c[0]: proj[c[0]]
                for c in cls._table_schema()
                if c[2]
            }
            for sub_f, sub_cls in cls.SUBTABLES.items():
                sub_projection = sub_cls._project_all(proj[sub_f])
                # add the parent row's pk data to the sub's fields
                for sub_val in sub_projection[sub_cls]:
                    sub_val.update(pk_vals)
                for ss_cls, ss_rows in sub_projection.items():
                    all_projected[ss_cls].extend(ss_rows)
        return all_projected

    @classmethod
    def _update_helper(cls, value: T) -> None:
        all_projected = cls._project_all([value])
        for storage_base, rows in all_projected.items():
            pk_names = {c[0] for c in storage_base._full_table_schema() if c[2]}
            val_names = list(n for n in rows[0].keys() if n not in pk_names)
            if not val_names:
                continue
            for row in rows:
                sql = f"UPDATE {storage_base.TABLE_NAME} SET "
                sql += ", ".join(f"{n} = :{n}" for n in val_names)
                sql += " WHERE "
                sql += " AND ".join(f"{n} = :{n}" for n in pk_names)
                current_session.get().connection.execute(sql, row)

    @classmethod
    def _get_val_type(cls) -> Type[T]:
        # assume cls inherits only from the storage base (which is to say us) or
        # object storage base, which is also specialized on T
        return cls.__orig_bases__[0].__args__[0]

    @classmethod
    def _delete_helper(cls, where_clauses: List[str], params: Dict[str, Any]) -> None:
        session = current_session.get()
        if not where_clauses:
            raise Exception("Probably unsafe to delete with no where clauses, refusing")
        if session.game_id is not None and cls.TABLE_NAME != "game":
            where_clauses.append("game_id = :game_id")
            params["game_id"] = session.game_id
        sql = f"DELETE FROM {cls.TABLE_NAME}"
        sql += " WHERE (" + ") AND (".join(where_clauses) + ")"
        session.connection.execute(sql, params)
        if cls.SUBTABLES:
            raise Exception("Subtable delete currently not supported")


class ValueStorageBase(StorageBase[str]):
    @classmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        return [("value", "text not null", True)]

    @classmethod
    def _construct_val(cls, row: Dict[str, Any]) -> str:
        return cast(str, row["value"])

    @classmethod
    def _project_val(cls, val: str) -> Dict[str, Any]:
        return {"value": val}


class ObjectStorageBase(StorageBase[T]):
    PRIMARY_KEYS: Set[str]

    @classmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        cols = []
        val_type = cls._get_val_type()
        for field_info in dataclass_fields(val_type):
            fname = field_info.name
            ftype = field_info.type
            if fname in cls.SUBTABLES:
                continue
            col_name = fname
            base_type = getattr(ftype, "__origin__", ftype)
            nn = " not null"
            if base_type == Union:  # ie, it was an optional
                # pull out the first type which is assumed to be the non-none type
                ftype = ftype.__args__[0]
                base_type = getattr(ftype, "__origin__", ftype)
                nn = " null"
            if base_type == int:
                col_type = "integer" + nn
            else:
                col_type = "text" + nn

            cols.append((col_name, col_type, col_name in cls.PRIMARY_KEYS))

        return cols

    @classmethod
    def _construct_val(cls, row: Dict[str, Any]) -> T:
        val_type = cls._get_val_type()
        # there's some subtly different behavior between the row object
        # (which is a sqlite3.Row) and a real dict which are causing problems
        # (in particular stuff around nullable fields and "key in row"), so just
        # converting to a regular dict before deserializing
        row = {k: row[k] for k in row.keys()}
        return recursive_from_dict(row, val_type)

    @classmethod
    def _project_val(cls, val: T) -> Dict[str, Any]:
        ret = {}
        val_type = cls._get_val_type()
        for field_info in dataclass_fields(val_type):
            fname = field_info.name
            ftype = field_info.type
            fval = getattr(val, fname)
            if fname in cls.SUBTABLES:
                ret[fname] = fval
            else:
                if ftype == Any:
                    indicator = val_type.type_field()
                    ftype = val_type.any_type(getattr(val, indicator))
                ret[fname] = cls._serialize_val(ftype, fval)
        return ret

    @classmethod
    def _serialize_val(cls, ftype: Type[T], fval: Any) -> Any:
        bt = getattr(ftype, "__origin__", ftype)
        if bt == Union:  # ie, it was an optional
            if fval is None:
                return None
            # pull out the first type which is assumed to be the non-none type
            ftype = ftype.__args__[0]  # type: ignore
            bt = getattr(ftype, "__origin__", ftype)

        if bt in (str, int, float, bool):
            return fval
        elif issubclass(bt, Enum):
            return fval.name
        else:
            return serialize(fval)


# Not strictly storage-related, but helpful in giving read-only views on some objects
# that are stored
class ReadOnlyWrapper:
    def __init__(self, data: Any) -> None:
        super().__setattr__("_fields", {f.name: f for f in dataclass_fields(data)})
        super().__setattr__("_data", data)
        self.z = -1

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._fields:
            raise Exception(f"Can't write {name}")
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if name in self._fields:
            val = getattr(self._data, name)
            ut = self._fields[name].type
            cls_base = getattr(ut, "__origin__", ut)
            if cls_base == Union:
                if val is None:
                    return None
                # pull out the first type which is assumed to be the non-none type
                ut = ut.__args__[0]
                cls_base = getattr(ut, "__origin__", ut)
            if cls_base == Any:
                indicator = self._data.type_field()
                cls_base = self._data.any_type(getattr(self._data, indicator))
            try:
                if issubclass(cls_base, Dict):
                    return MappingProxyType(val)
                elif cls_base not in (str, tuple) and issubclass(cls_base, Iterable):
                    return tuple(val)
                else:
                    return val
            except Exception:
                print(f"Bad type reading field {name} ({ut}, {cls_base}, {val})")
                raise
        else:
            raise Exception(f"No such field: {name}")
