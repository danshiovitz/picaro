from typing import Any, Dict, List, Optional, Sequence, Tuple

from .board import BoardRules
from .types.common import EntityType
from .types.store import Entity, Gadget, Token


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
