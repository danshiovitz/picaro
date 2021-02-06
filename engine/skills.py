#!/usr/bin/python3

from typing import Any, Dict, List

from .storage import ValueStorageBase

def load_skills() -> List[str]:
    return SkillsStorage.load()

class SkillsStorage(ValueStorageBase):
    TABLE_NAME = "skill"

    @classmethod
    def load(cls) -> List[str]:
        return cls._select_helper([], {}, active_conn=None)
