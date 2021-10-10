from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .base import StandardStorage, StandardWrapper
from .common_types import EntityType


@dataclass
class EntityStorage(StandardStorage["EntityStorage"]):
    TABLE_NAME = "entity"

    uuid: str
    type: EntityType
    subtype: Optional[str]
    name: str

    @classmethod
    def load_by_name(cls, name: str) -> "EntityStorage":
        entities = cls._select_helper(["name = :name"], {"name": name})
        if not entities:
            raise IllegalMoveException(f"No such entity: {name}")
        return entities[0]


class Entity(StandardWrapper[EntityStorage]):
    @classmethod
    def load_by_name(cls, name: str) -> "Entity":
        data = EntityStorage.load_by_name(name)
        return Entity(data)
