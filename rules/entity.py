from typing import Any, Dict, List, Optional, Sequence, Tuple

from picaro.store.board import Token
from picaro.store.common_types import EntityType
from picaro.store.entity import Entity
from picaro.store.gadget import Gadget

from .board import BoardRules


class EntityRules:
    @classmethod
    def create(
        cls,
        name: str,
        type: EntityType,
        subtype: Optional[str],
        locations: Sequence[str],
    ) -> str:
        uuid = Entity.create(name=name, type=type, subtype=subtype)
        for location in locations:
            if location == "random":
                location = BoardRules.get_random_hex().name
            Token.create(entity=uuid, location=location)
        return uuid
