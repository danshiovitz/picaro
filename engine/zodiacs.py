from typing import Any, Dict, List

from .storage import ValueStorageBase

def load_zodiacs() -> List[str]:
    return ZodiacStorage.load()

class ZodiacStorage(ValueStorageBase):
    TABLE_NAME = "zodiac"

    @classmethod
    def load(cls) -> List[str]:
        return cls._select_helper([], {}, active_conn=None)
