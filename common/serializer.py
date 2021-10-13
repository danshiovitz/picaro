import json
from collections.abc import Sequence
from dataclasses import _MISSING_TYPE, fields as dataclass_fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Type, TypeVar, Union


T = TypeVar("T")


def serialize(
    val: T, cls: Optional[Type[T]] = None, indent: Optional[int] = None
) -> str:
    if cls is None:
        cls = type(val)
    safe = to_safe_type(val, cls)
    return json.dumps(safe, indent=indent)


# convert val to a "safe type":
# - a primitive (str, int, float, bool, None)
# - a list or dict of safe types
# - enums are converted to their name (a string), dataclasses to dicts
def to_safe_type(
    val: Any, cls: Type[Any], any_type: Optional[Type[Any]] = None, path: str = ""
) -> Any:
    try:
        return _to_safe_type(val, cls, any_type, path)
    except Exception as e:
        print(f"Error converting to type at {path}: {e}")
        raise


def _to_safe_type(
    val: Any, cls: Type[Any], any_type: Optional[Type[Any]], path: str
) -> Any:
    while True:
        cls_base = getattr(cls, "__origin__", cls)
        if cls_base == Union:  # ie, it was an optional
            if val is None:
                return None
            # pull out the first type which is assumed to be the non-none type
            cls = cls.__args__[0]
            continue

        if cls == Any:
            if any_type is None:
                raise Exception("Found Any without any_type")
            cls = any_type
            continue

        if isinstance(cls, TypeVar):
            # hack, assumes this dataclass is templated on a single variable only
            # cls.__args__[0]
            raise Exception("Found TypeVar, currently not supported")

        break

    if cls_base in (str, int, float, bool, type(None)):
        if type(val) != cls_base:
            raise Exception(f"Type mismatch: expected {cls_base}, found {type(val)}")
        return val
    elif issubclass(cls_base, Enum):
        return val.name
    elif val is None:
        return None
    elif is_dataclass(cls_base):
        ret = {}
        cur_any: Optional[Type[Any]] = None
        if hasattr(cls_base, "type_field"):
            indicator = cls_base.type_field()
            cur_any = cls_base.any_type(getattr(val, indicator))

        for field in dataclass_fields(cls_base):
            field_val = getattr(val, field.name)
            ret[field.name] = to_safe_type(
                field_val, field.type, cur_any, path + "." + field.name
            )
        return ret
    elif issubclass(cls_base, tuple):
        exp_types = getattr(cls, "__args__", [type(None)] * len(val))
        return [
            to_safe_type(sv, exp_types[idx], None, path + "()")
            for idx, sv in enumerate(val)
        ]
    elif issubclass(cls_base, Dict):
        exp_types = getattr(cls, "__args__", [type(None), type(None)])
        return {
            to_safe_type(k, exp_types[0], None, path + "{k}"): to_safe_type(
                v, exp_types[1], None, path + "{v}"
            )
            for k, v in val.items()
        }
    elif issubclass(cls_base, Iterable):
        exp_types = getattr(cls, "__args__", [type(None)])
        return [to_safe_type(sv, exp_types[0], None, path + "[]") for sv in val]
    else:
        raise Exception(f"Unserializable type {cls_base}")


def deserialize(data: Any, cls: Type[T], frozen: Optional[bool] = None) -> T:
    safe = json.loads(data)
    return from_safe_type(safe, cls, frozen)


def logged_load(val: str) -> Any:
    try:
        return json.loads(val)
    except json.decoder.JSONDecodeError:
        print(f"Bad json: {repr(val)}")
        raise


def from_safe_type(
    val: Any,
    cls: Type[T],
    any_type: Optional[Type[Any]] = None,
    frozen: Optional[bool] = None,
    path: str = "",
) -> T:
    try:
        return _from_safe_type(val, cls, any_type, frozen, path)
    except Exception as e:
        print(f"Error deserializing at {path}: {e}")
        raise


def _from_safe_type(
    val: Any,
    cls: Type[T],
    any_type: Optional[Type[Any]],
    frozen: Optional[bool],
    path: str = "",
) -> T:
    while True:
        cls_base = getattr(cls, "__origin__", cls)
        if cls_base == Union:  # ie, it was an optional
            if val is None:
                return None
            # pull out the first type which is assumed to be the non-none type
            cls = cls.__args__[0]
            continue

        if cls == Any:
            if any_type is None:
                raise Exception("Found Any without any_type")
            cls = any_type
            continue

        if isinstance(cls, TypeVar):
            # hack, assumes this dataclass is templated on a single variable only
            # cls.__args__[0]
            raise Exception("Found TypeVar, currently not supported")

        break

    if cls_base in (str, type(None)):
        if type(val) != cls_base:
            raise Exception(f"Type mismatch: expected {cls_base}, found {type(val)}")
        return val
    elif cls_base in (int, float):
        # in particular when deserializing dicts, keys can get forced to strings
        # even when they're not intended as such
        return cls_base(val)
    elif cls_base == bool:
        # this gets serialized weird in sqlite for some reason
        return val not in ("0", 0, False)
    elif issubclass(cls_base, Enum):
        return cls[val]
    elif val is None:
        return None
    elif is_dataclass(cls_base):
        if type(val) == str:
            val = logged_load(val)
        if type(val) != dict:
            raise Exception(f"Got {type(val)} for dataclass, expected dict")
        if frozen is None:
            frozen = cls_base.__dataclass_params__.frozen

        params = {}

        fields = dataclass_fields(cls_base)

        def lookup(field, any_repl) -> Any:
            if field.name not in val and not isinstance(field.default, _MISSING_TYPE):
                return field.default
            else:
                return from_safe_type(
                    val[field.name],
                    field.type,
                    any_repl,
                    frozen,
                    path + "." + field.name,
                )

        cur_any: Optional[Type[Any]] = None
        if hasattr(cls_base, "type_field"):
            indicator = cls_base.type_field()
            ind_field = [f for f in fields if f.name == indicator][0]
            cur_any = cls_base.any_type(lookup(ind_field, any_type))

        for field in fields:
            params[field.name] = lookup(field, cur_any)

        return cls(**params)
    elif issubclass(cls_base, tuple):
        if type(val) == str:
            val = logged_load(val)
        exp_types = getattr(cls, "__args__", [type(None)] * len(val))
        return tuple(
            from_safe_type(sv, exp_types[idx], None, True, path + "()")
            for idx, sv in enumerate(val)
        )
    elif issubclass(cls_base, Dict):
        if type(val) == str:
            val = logged_load(val)
        exp_types = getattr(cls, "__args__", [type(None), type(None)])
        return {
            from_safe_type(k, exp_types[0], None, frozen, path + "{k}"): from_safe_type(
                v, exp_types[1], None, frozen, path + "{v}"
            )
            for k, v in val.items()
        }
    elif issubclass(cls_base, Iterable):
        if type(val) == str:
            val = logged_load(val)
        exp_types = getattr(cls, "__args__", [type(None)])
        seq = (
            from_safe_type(sv, exp_types[0], None, frozen, path + "[]") for sv in val
        )
        return tuple(seq) if frozen or cls_base == Sequence else cls_base(seq)
    else:
        raise Exception(f"Un(de)serializable type {cls_base}")
