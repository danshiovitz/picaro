#!/usr/bin/python3

from typing import List, NamedTuple

from .load import load_json


class SkillsStruct(NamedTuple):
    names: List[str]


def load_skills() -> List[str]:
    loaded = load_json("skills", SkillsStruct)
    return loaded.names
