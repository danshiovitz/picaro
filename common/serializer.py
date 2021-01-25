import json
from enum import Enum
from typing import Any, Dict, Optional, NamedTuple, Sequence, Type, TypeVar, Union

def serialize(val: NamedTuple, indent: Optional[int] = None) -> str:
    if not hasattr(val, "_fields"):
        raise Exception(f"{val} is not the right type: {val.__class__.__name__}")
    dt = recursive_to_dict(val)
    return json.dumps(dt, indent=indent)


T = TypeVar("T")
def deserialize(data: str, cls: Type[T]) -> T:
    if not hasattr(cls, "_fields"):
        raise Exception(f"{cls.__name__} is not a subclass of NamedTuple")
    dt = json.loads(data)
    return recursive_from_dict(dt, cls)


def recursive_to_dict(val: T, cls: Type[T] = type(None)) -> Any:
    if cls == type(None):
        cls = type(val)
    cls_base = getattr(cls, "__origin__", cls)
    if hasattr(cls, "_fields"):
        ret = {}
        for f in val._fields:
            subv = getattr(val, f)
            ut = val._field_types[f]
            bt = getattr(ut, "__origin__", ut)
            if bt == Union: # ie, it was an optional
                if subv is None:
                    ret[f] = None
                    continue
                # pull out the first type which is assumed to be the non-none type
                ut = val._field_types[f].__args__[0]
                bt = getattr(ut, "__origin__", ut)
            ret[f] = recursive_to_dict(subv, ut)
        return ret
    elif issubclass(cls_base, tuple):
        return [recursive_to_dict(sv, cls.__args__[idx]) for idx, sv in enumerate(val)]
    elif cls_base != str and issubclass(cls_base, Sequence):
        return [recursive_to_dict(sv, cls.__args__[0]) for sv in val]
    elif issubclass(cls_base, Dict):
        return {recursive_to_dict(k, cls.__args__[0]): recursive_to_dict(v, cls.__args__[1]) for k, v in val.items()}
    elif issubclass(cls_base, Enum):
        return val.name
    else:
        return val

def recursive_from_dict(val: Any, cls: Type[T]) -> T:
    cls_base = getattr(cls, "__origin__", cls)
    if hasattr(cls, "_fields"):
        dt = {}
        for f in val:
            ut = cls._field_types[f]
            bt = getattr(cls._field_types[f], "__origin__", cls._field_types[f])
            if bt == Union: # ie, it was an optional
                if val[f] is None:
                    dt[f] = None
                    continue
                # pull out the first type which is assumed to be the non-none type
                ut = cls._field_types[f].__args__[0]
                bt = getattr(ut, "__origin__", ut)
            dt[f] = recursive_from_dict(val[f], ut)
        return cls(**dt)
    elif issubclass(cls_base, tuple):
        return tuple(recursive_from_dict(sv, cls.__args__[idx]) for idx, sv in enumerate(val))
    elif cls_base != str and issubclass(cls_base, Sequence):
        return [recursive_from_dict(sv, cls.__args__[0]) for sv in val]
    elif issubclass(cls_base, Dict):
        return {recursive_from_dict(k, cls.__args__[0]): recursive_from_dict(v, cls.__args__[1]) for k, v in val.items()}
    elif issubclass(cls_base, Enum):
        return cls[val]
    else:
        return val
