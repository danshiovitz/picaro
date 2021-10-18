import functools
import inspect
import json
import random
from contextvars import ContextVar
from dataclasses import dataclass, fields as dataclass_fields, Field as dataclass_Field
from enum import Enum
from pathlib import Path
from sqlite3 import Connection, Row, connect
from string import ascii_lowercase
from types import MappingProxyType, TracebackType
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
)

from .exceptions import BadStateException
from .serializer import from_safe_type, to_safe_type


@dataclass
class Session:
    player_uuid: Optional[str]
    game_uuid: Optional[str]
    connection: Connection


current_session: ContextVar[Session] = ContextVar("current_session")
all_stores: Set[Type["StorageBase[Any]"]] = set()


T = TypeVar("T")


class StorageBase(Generic[T]):
    TABLE_NAME = "unset"
    PRIMARY_KEYS: Set[str]
    UNIQUE_KEYS: Set[str] = set()
    SECONDARY_TABLE: bool = False
    LOAD_KEY: Optional[str] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore
        if cls.TABLE_NAME != "unset":
            all_stores.add(cls)

    # list of (name, type, is_primary) columns
    @classmethod
    def _table_schema(cls) -> List[Tuple[str, str, bool]]:
        cols = []
        val_type = cls._get_val_type()
        for field_info in dataclass_fields(val_type):
            fname = field_info.name
            ftype = field_info.type
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
            if fname in cls.UNIQUE_KEYS:
                col_type += " unique"
            cols.append((col_name, col_type, col_name in cls.PRIMARY_KEYS))

        if cls.TABLE_NAME != "game":
            cols = [("game_uuid", "text not null", True)] + cols

        return cols

    # construct a single T object based on the given row
    @classmethod
    def _construct_val(cls, row: Dict[str, Any]) -> T:
        val_type = cls._get_val_type()
        # there's some subtly different behavior between the row object
        # (which is a sqlite3.Row) and a real dict which are causing problems
        # (in particular stuff around nullable fields and "key in row"), so just
        # converting to a regular dict before deserializing
        row = {k: row[k] for k in row.keys()}
        return from_safe_type(row, val_type)

    # convert a single T object into a row
    @classmethod
    def _project_val(cls, val: T) -> Dict[str, Any]:
        ret = {}
        val_type = cls._get_val_type()
        try:
            safe_dict = to_safe_type(val, val_type)
        except:
            print(f"Failure to project: {val}")
            raise
        for k, v in safe_dict.items():
            if type(v) not in (str, int, float, bool, type(None)):
                v = json.dumps(v)
            ret[k] = v

        if cls.TABLE_NAME != "game":
            session = current_session.get()
            if session.game_uuid is not None:
                ret["game_uuid"] = session.game_uuid

        return ret

    @classmethod
    def _get_val_type(cls) -> Type[T]:
        return cls

    @classmethod
    def _initialize(cls) -> None:
        cols = cls._table_schema()
        sql = f"CREATE TABLE {cls.TABLE_NAME} (\n  "
        sql += ",\n  ".join(f"{c[0]} {c[1]}" for c in cols)
        pks = ", ".join(c[0] for c in cols if c[2])
        sql += f",\n  primary key ({pks})"
        sql += "\n)"
        current_session.get().connection.execute(sql, {})

    @classmethod
    def _select_helper(
        cls, where_clauses: List[str], params: Dict[str, Any]
    ) -> List[T]:
        session = current_session.get()
        if session.game_uuid is not None:
            if cls.TABLE_NAME != "game":
                where_clauses.append("game_uuid = :game_uuid")
            else:
                where_clauses.append("uuid = :game_uuid")
            params["game_uuid"] = session.game_uuid

        sql = f"SELECT * FROM {cls.TABLE_NAME}"
        if where_clauses:
            sql += " WHERE (" + ") AND (".join(where_clauses) + ")"

        ret: List[T] = []
        for row in session.connection.execute(sql, params):
            ret.append(cls._construct_val(row))
        return ret

    @classmethod
    def _insert_helper(cls, values: List[T]) -> None:
        # can get issues with max param count in sqlite when inserting
        # too many fields at once, so chunk it:
        for idx in range(0, len(values), 20):
            rows = [cls._project_val(v) for v in values[idx : idx + 20]]
            names = list(n for n in rows[0].keys())
            each_params = tuple(row[n] for row in rows for n in names)
            values_clause = "(" + ", ".join("?" for _ in names) + ")"
            sql = f"INSERT INTO {cls.TABLE_NAME} ("
            sql += ", ".join(n for n in names)
            sql += ") VALUES " + ", ".join(values_clause for _ in rows)
            current_session.get().connection.execute(sql, each_params)

    @classmethod
    def _update_helper(cls, value: T) -> None:
        row = cls._project_val(value)
        pk_names = {c[0] for c in cls._table_schema() if c[2]}
        val_names = list(n for n in row.keys() if n not in pk_names)
        if not val_names:
            return
        sql = f"UPDATE {cls.TABLE_NAME} SET "
        sql += ", ".join(f"{n} = :{n}" for n in val_names)
        sql += " WHERE "
        sql += " AND ".join(f"{n} = :{n}" for n in pk_names)
        current_session.get().connection.execute(sql, row)

    @classmethod
    def _delete_helper(cls, where_clauses: List[str], params: Dict[str, Any]) -> None:
        session = current_session.get()
        if not where_clauses:
            raise Exception("Probably unsafe to delete with no where clauses, refusing")
        if session.game_uuid is not None and cls.TABLE_NAME != "game":
            where_clauses.append("game_uuid = :game_uuid")
            params["game_uuid"] = session.game_uuid
        sql = f"DELETE FROM {cls.TABLE_NAME}"
        sql += " WHERE (" + ") AND (".join(where_clauses) + ")"
        session.connection.execute(sql, params)


class ConnectionManager:
    DB_STR: str = "UNSET"
    MEMORY_CONNECTION_HANDLE: Optional[Connection] = None

    @classmethod
    def initialize(cls, db_path: Optional[str]) -> None:
        if db_path:
            cls.DB_STR = f"file:{db_path}"
        else:
            cls.DB_STR = "file:ephemeral_db?mode=memory&cache=shared"
            # actually go ahead and open a connection to this shared memory
            # so it'll stick around for the program
            if cls.MEMORY_CONNECTION_HANDLE:
                cls.MEMORY_CONNECTION_HANDLE.close()
            cls.MEMORY_CONNECTION_HANDLE = connect(cls.DB_STR, uri=True)

        with ConnectionManager(player_uuid=None, game_uuid=None):
            for store_cls in all_stores:
                store_cls._initialize()

    def __init__(self, player_uuid: Optional[str], game_uuid: Optional[str]) -> None:
        if self.DB_STR == "UNSET":
            raise Exception("ConnectionManager not initialized")

        self.player_uuid = player_uuid
        self.game_uuid = game_uuid

    def __enter__(self) -> "ConnectionManager":
        if current_session.get(None) is not None:
            raise Exception(
                "Trying to create a nested connection, this is probably bad"
            )
        connection = connect(self.DB_STR, uri=True)
        connection.row_factory = Row
        connection.__enter__()  # type: ignore
        session = Session(
            player_uuid=self.player_uuid,
            game_uuid=self.game_uuid,
            connection=connection,
        )
        self.ctx_token = current_session.set(session)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: TracebackType,
    ) -> None:
        session = current_session.get()
        current_session.reset(self.ctx_token)
        session.connection.__exit__(exc_type, exc_val, exc_tb)  # type: ignore

    @classmethod
    def fix_game_uuid(cls, game_uuid: str) -> None:
        session = current_session.get()
        session.game_uuid = game_uuid


def with_connection() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            game_uuid = kwargs.get("game_uuid", None)
            player_uuid = kwargs.get("player_uuid", None)
            with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def make_uuid() -> str:
    return "".join(random.choice(ascii_lowercase) for _ in range(12))


def make_double_uuid(base_id: str) -> str:
    return base_id + "." + make_uuid()


def get_parent_uuid(uuid: str) -> str:
    if "." not in uuid:
        raise Exception(f"Not right format to split? {uuid}")
    return uuid.split(".")[0]


class StandardWrapper:
    FIELDS: Dict[str, dataclass_Field]
    Data: Type[Any]

    def __init__(self, data: Any, can_write: bool = False) -> None:
        if not isinstance(data, self.Data):
            raise Exception(
                f"Bad initialization - expected {self.Data.__name__}, got {data.__class__.__name__}"
            )
        super().__setattr__("_data", data)
        super().__setattr__("_can_write", can_write)
        super().__setattr__("_write", False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore
        cls.Data = dataclass(cls.Data)
        cls.FIELDS = {f.name: f for f in dataclass_fields(cls.Data)}
        if "uuid" in cls.FIELDS:
            cls.HAS_UUID = True
            cls.Data.PRIMARY_KEYS = {"uuid"}
        elif "name" in cls.FIELDS:
            cls.HAS_UUID = False
            cls.Data.PRIMARY_KEYS = {"name"}
        else:
            raise Exception(f"Can't figure out pk for class from {cls.FIELDS}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.FIELDS:
            if self._write:
                self._data.__setattr__(name, value)
            else:
                raise Exception(f"Can't write {name}")
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if name in self.FIELDS:
            val = getattr(self._data, name)
            if self._write:
                return val
            ut = self.FIELDS[name].type
            cls_base = getattr(ut, "__origin__", ut)
            if cls_base == Union:
                if val is None:
                    return None
                # pull out the first type which is assumed to be the non-none type
                ut = ut.__args__[0]
                cls_base = getattr(ut, "__origin__", ut)
            if cls_base == Any:
                indicator = self._data.type_field()
                ut = self._data.any_type(getattr(self._data, indicator))
                cls_base = getattr(ut, "__origin__", ut)
            if cls_base == Union:
                if val is None:
                    return None
                # pull out the first type which is assumed to be the non-none type
                ut = ut.__args__[0]
                cls_base = getattr(ut, "__origin__", ut)
            try:
                if issubclass(cls_base, dict):
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

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StandardWrapper) or self.Data != other.Data:
            return NotImplemented
        return self._data.__eq__(other._data)

    def __hash__(self) -> int:
        raise Exception("Shouldn't hash this type")

    @classmethod
    def load(cls, key: str) -> Any:  # should be type(self)
        pk_field = cls.Data.LOAD_KEY or list(cls.Data.PRIMARY_KEYS)[0]
        return cls._load_helper_single([f"{pk_field} = :{pk_field}"], {pk_field: key})

    @classmethod
    def load_all(cls) -> List[Any]:  # should be type(self)
        return cls._load_helper([], {})

    @classmethod
    def load_for_write(cls, key: str) -> Any:  # should be type(self)
        pk_field = cls.Data.LOAD_KEY or list(cls.Data.PRIMARY_KEYS)[0]
        return cls._load_helper_single(
            [f"{pk_field} = :{pk_field}"], {pk_field: key}, can_write=True
        )

    @classmethod
    def _load_helper(
        cls, where_clauses: List[str], params: Dict[str, Any], can_write: bool = False
    ) -> List[Any]:  # should be type(self)
        data_lst = cls.Data._select_helper(where_clauses, params)
        return [cls(d, can_write=can_write) for d in data_lst]

    @classmethod
    def _load_helper_single(
        cls, where_clauses: List[str], params: Dict[str, Any], can_write: bool = False
    ) -> Any:  # should be type(self)
        vals = cls._load_helper(where_clauses, params, can_write)
        if not vals:
            raise BadStateException(f"No such {cls.Data.TABLE_NAME}: {params}")
        return vals[0]

    def __enter__(self) -> Any:  # should be type(self)
        if not self._can_write:
            raise Exception("This is only useful if loaded writeable!")
        self._write = True
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: TracebackType,
    ) -> None:
        # we only commit the changes if no exception was thrown - this is a little
        # redundant with the fact that we won't commit the transaction as a whole
        # if an exception is thrown, but it seems like it'll cover a few edge cases,
        # and it makes testing easier
        if not exc_val:
            type(self).Data._update_helper(self._data)

    # Note this returns an object with write=True that nevertheless isn't
    # persisted automatically, but it is writeable
    @classmethod
    def create_detached(cls, **kwargs) -> Any:  # should be type(self)
        if cls.HAS_UUID and not cls.Data.SECONDARY_TABLE:
            kwargs["uuid"] = make_uuid()
        ret = cls(cls.Data(**kwargs), can_write=True)
        ret._write = True
        return ret

    @classmethod
    def insert(cls, vals: List[Any]) -> None:  # should be type(self)
        cls.Data._insert_helper([v._data for v in vals])

    @classmethod
    def create(cls, **kwargs) -> Optional[str]:
        val = cls.create_detached(**kwargs)
        cls.insert([val])
        if cls.HAS_UUID:
            return val.uuid
        return None
