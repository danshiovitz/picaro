from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
)

from picaro.common.exceptions import IllegalMoveException

from .base import StandardStorage, StandardWrapper
from .common_types import (
    Action,
    Encounter,
    FullCard,
    TableauCard,
    TemplateCard,
    TravelCard,
)
from .entity import Entity


class TurnFlags(Enum):
    ACTED = enum_auto()
    HAD_TRAVEL_ENCOUNTER = enum_auto()
    BAD_REP_CHECKED = enum_auto()


@dataclass
class CharacterStorage(StandardStorage["CharacterStorage"]):
    TABLE_NAME = "character"
    SECONDARY_TABLE = True

    uuid: str
    player_uuid: str
    job_name: str
    skill_xp: Dict[str, int]
    health: int
    coins: int
    resources: Dict[str, int]
    reputation: int
    remaining_turns: int
    luck: int
    turn_flags: Set[TurnFlags]
    speed: int
    tableau: List[TableauCard]
    encounter: Optional[Encounter]
    queued: List[FullCard]
    job_deck: List[TemplateCard]
    travel_deck: List[TravelCard]
    camp_deck: List[TemplateCard]


class Character(StandardWrapper[CharacterStorage]):
    @classmethod
    def load_by_name(cls, character_name: str) -> "Character":
        # this is going to be so common, let's support it here:
        entity = Entity.load_by_name(character_name)
        data = CharacterStorage.load(entity.uuid)
        return Character(data)

    @classmethod
    def load_by_name_for_write(cls, character_name: str) -> "Character":
        # this is going to be so common, let's support it here:
        entity = Entity.load_by_name(character_name)
        data = CharacterStorage.load(entity.uuid)
        return Character(data, can_write=True)

    def acted_this_turn(self) -> None:
        return TurnFlags.ACTED in self._data.turn_flags

    def check_set_flag(self, flag: TurnFlags) -> bool:
        if not self._write:
            raise Exception(f"Can't set flag on non-writable character")
        prev = flag in self._data.turn_flags
        self._data.turn_flags.add(flag)
        return not prev

    def has_encounters(self) -> bool:
        return self.encounter or self.queued
