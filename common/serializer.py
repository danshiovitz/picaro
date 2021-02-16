import json
from dataclasses import fields as dataclass_fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Type, TypeVar, Union


def serialize(val: Any, indent: Optional[int] = None) -> str:
    dt = recursive_to_dict(val)
    return json.dumps(dt, indent=indent)


T = TypeVar("T")


def deserialize(data: str, cls: Type[T], frozen: Optional[bool] = None) -> T:
    dt = json.loads(data)
    return recursive_from_dict(dt, cls, frozen)


def recursive_to_dict(val: T, cls: Type[T] = type(None)) -> Any:
    if cls == type(None):
        cls = type(val)
    cls_base = getattr(cls, "__origin__", cls)

    if is_dataclass(cls_base):
        ret = {}
        for field in dataclass_fields(cls_base):
            subv = getattr(val, field.name)
            ut = field.type
            bt = getattr(ut, "__origin__", ut)
            if bt == Union:  # ie, it was an optional
                if subv is None:
                    ret[field.name] = None
                    continue
                # pull out the first type which is assumed to be the non-none type
                ut = field.type.__args__[0]
                bt = getattr(ut, "__origin__", ut)
            # hack, assumes this dataclass is templated on a single variable only
            if isinstance(ut, TypeVar):
                ut = cls.__args__[0]
            ret[field.name] = recursive_to_dict(subv, ut)
        return ret
    elif issubclass(cls_base, tuple):
        exp_types = getattr(cls, "__args__", [type(None)] * len(val))
        return [recursive_to_dict(sv, exp_types[idx]) for idx, sv in enumerate(val)]
    elif cls_base != str and issubclass(cls_base, Sequence):
        exp_types = getattr(cls, "__args__", [type(None)])
        return [recursive_to_dict(sv, exp_types[0]) for sv in val]
    elif issubclass(cls_base, Dict):
        exp_types = getattr(cls, "__args__", [type(None), type(None)])
        return {
            recursive_to_dict(k, exp_types[0]): recursive_to_dict(v, exp_types[1])
            for k, v in val.items()
        }
    elif issubclass(cls_base, Enum):
        return val.name
    else:
        return val


def recursive_from_dict(val: Any, cls: Type[T], frozen: Optional[bool] = None) -> T:
    cls_base = getattr(cls, "__origin__", cls)

    def logged_load(val: str) -> Any:
        try:
            return json.loads(val)
        except json.decoder.JSONDecodeError:
            print(f"Bad json: {repr(val)}")
            raise

    if is_dataclass(cls_base):
        if frozen is None:
            frozen = cls_base.__dataclass_params__.frozen
        dt = {}
        for field in dataclass_fields(cls_base):
            ut = field.type
            bt = getattr(ut, "__origin__", ut)
            if bt == Union:  # ie, it was an optional
                if val[field.name] is None:
                    dt[field.name] = None
                    continue
                # pull out the first type which is assumed to be the non-none type
                ut = ut.__args__[0]
                bt = getattr(ut, "__origin__", ut)
            # hack, assumes this dataclass is templated on a single variable only
            if isinstance(ut, TypeVar):
                ut = cls.__args__[0]
            dt[field.name] = recursive_from_dict(val[field.name], ut, frozen)
        return cls(**dt)
    elif issubclass(cls_base, tuple):
        if type(val) == str:
            val = logged_load(val)
        return tuple(
            recursive_from_dict(sv, cls.__args__[idx], frozen)
            for idx, sv in enumerate(val)
        )
    elif cls_base != str and issubclass(cls_base, Sequence):
        if type(val) == str:
            val = logged_load(val)
        seq = (recursive_from_dict(sv, cls.__args__[0], frozen) for sv in val)
        return tuple(seq) if frozen else list(seq)
    elif issubclass(cls_base, Dict):
        if type(val) == str:
            val = logged_load(val)
        return {
            recursive_from_dict(k, cls.__args__[0], frozen): recursive_from_dict(
                v, cls.__args__[1], frozen
            )
            for k, v in val.items()
        }
    elif issubclass(cls_base, Enum):
        return cls[val]
    elif cls_base == bool:
        # this gets serialized weird in sqlite for some reason
        return val not in ("0", 0, False)
    else:
        return val
