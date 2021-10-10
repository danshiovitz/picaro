from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Union

from .base import StandardStorage, StandardWrapper
from .common_types import EffectType, TemplateCard
from .gadget import Gadget


@dataclass
class RecordStorage(StandardStorage["RecordStorage"]):
    TABLE_NAME = "record"

    uuid: str
    entity_uuid: str
    type: EffectType
    subtype: Optional[str]
    old_value: Any
    new_value: Any
    comments: Sequence[str]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EffectType, str]) -> type:
        if type(type_val) is str:
            type_val = EffectType[type_val]

        if type_val == EffectType.ADD_EMBLEM:
            return Gadget
        elif type_val == EffectType.QUEUE_ENCOUNTER:
            return Optional[TemplateCard]
        elif type_val in (
            EffectType.MODIFY_JOB,
            EffectType.MODIFY_LOCATION,
        ):
            return str
        else:
            return int


class Record(StandardWrapper[RecordStorage]):
    pass
