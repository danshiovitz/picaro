#!/usr/bin/python3

from typing import List, NamedTuple

from .load import load_json


class ZodiacsStruct(NamedTuple):
    names: List[str]


def load_zodiacs() -> List[str]:
    loaded = load_json("zodiacs", ZodiacsStruct)
    return loaded.names
