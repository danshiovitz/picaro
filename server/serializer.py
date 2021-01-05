import json
from typing import Any, Dict, NamedTuple, Sequence, Type, TypeVar

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


def recursive_to_dict(val: NamedTuple) -> str:
    ret = {}
    for f in val._fields:
        subv = getattr(val, f)
        bt = getattr(val._field_types[f], "__origin__", val._field_types[f])
        if hasattr(bt, "_fields"):
            ret[f] = recursive_to_dict(subv)
        elif bt != str and issubclass(bt, Sequence):
            ret[f] = [recursive_to_dict(sv) for sv in subv]
        elif issubclass(bt, Dict):
            ret[f] = {k: recursive_to_dict(v) for k, v in subv.items()}
        else:
            ret[f] = subv
    return ret


def recursive_from_dict(val: Dict[str, Any], cls: Type[T]) -> T:
    dt = {}
    for f in cls._fields:
        bt = getattr(cls._field_types[f], "__origin__", cls._field_types[f])
        if hasattr(bt, "_fields"):
            dt[f] = recursive_from_dict(val[f], bt)
        elif bt != str and issubclass(bt, Sequence):
            dt[f] = [recursive_from_dict(sv, cls._field_types[f].__args__[0]) for sv in val[f]]
        elif issubclass(bt, Dict):
            dt[f] = {k: recursive_from_dict(v, cls._field_types[f].__args__[1]) for k, v in val[f].items()}
        else:
            dt[f] = val[f]
    return cls(**dt)
