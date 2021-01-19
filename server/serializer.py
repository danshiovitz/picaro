import json
from enum import Enum
from typing import Any, Dict, NamedTuple, Sequence, Type, TypeVar, Union

def serialize(val: NamedTuple) -> str:
    if not hasattr(val, "_fields"):
        raise Exception(f"{val} is not the right type: {val.__class__.__name__}")
    dt = recursive_to_dict(val)
    return json.dumps(dt)


T = TypeVar("T")
def deserialize(data: str, cls: Type[T]) -> T:
    if not hasattr(cls, "_fields"):
        raise Exception(f"{cls.__name__} is not a subclass of NamedTuple")
    dt = json.loads(data)
    return recursive_from_dict(dt, cls)


def recursive_to_dict(val: T, cls: Type[T] = type(None)) -> Dict[str, Any]:
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

            if hasattr(bt, "_fields"):
                ret[f] = recursive_to_dict(subv, ut)
            elif bt != str and issubclass(bt, Sequence):
                ret[f] = [recursive_to_dict(sv, ut.__args__[0]) for sv in subv]
            elif issubclass(bt, Dict):
                ret[f] = {k: recursive_to_dict(v, ut.__args__[1]) for k, v in subv.items()}
            else:
                ret[f] = recursive_to_dict(subv, ut)
        return ret
    elif issubclass(cls_base, Enum):
        return val.name
    else:
        return val

def recursive_from_dict(val: Dict[str, Any], cls: Type[T]) -> T:
    if not hasattr(cls, "_fields"):
        return val

    dt = {}
    for f in cls._fields:
        ut = cls._field_types[f]
        bt = getattr(cls._field_types[f], "__origin__", cls._field_types[f])
        if bt == Union: # ie, it was an optional
            if val[f] is None:
                dt[f] = None
                continue
            # pull out the first type which is assumed to be the non-none type
            ut = cls._field_types[f].__args__[0]
            bt = getattr(ut, "__origin__", ut)

        if hasattr(bt, "_fields"):
            dt[f] = recursive_from_dict(val[f], bt)
        elif bt != str and issubclass(bt, Sequence):
            dt[f] = [recursive_from_dict(sv, ut.__args__[0]) for sv in val[f]]
        elif issubclass(bt, Dict):
            dt[f] = {k: recursive_from_dict(v, ut.__args__[1]) for k, v in val[f].items()}
        else:
            dt[f] = val[f]
    return cls(**dt)
