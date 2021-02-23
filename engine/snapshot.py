from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Sequence

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.types import (
    Action,
    ChoiceType,
    TableauCard,
    Effect,
    Emblem,
    EncounterCheck,
)


@dataclass(frozen=True)
class Hex:
    name: str
    coordinate: OffsetCoordinate
    terrain: str
    country: str
    region: str
    danger: int


@dataclass(frozen=True)
class Token:
    name: str
    type: str
    location: str
    actions: Sequence[Action]
    route: Sequence[str]


@dataclass(frozen=True)
class Board:
    hexes: Sequence[Hex]
    tokens: Sequence[Token]


@dataclass(frozen=True)
class TableauCard:
    id: str
    name: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
    age: int
    location: str
    route: Sequence[str]


@dataclass(frozen=True)
class Encounter:
    name: str
    desc: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
    signs: Sequence[str]
    rolls: Sequence[int]


@dataclass(frozen=True)
class Character:
    name: str
    player_id: int
    skills: Dict[str, int]
    skill_xp: Dict[str, int]
    job: str
    health: int
    coins: int
    resources: int
    reputation: int
    quest: int
    location: str
    remaining_turns: int
    acted_this_turn: bool
    luck: int
    speed: int
    tableau: Sequence[TableauCard]
    encounters: Sequence[Encounter]
    emblems: Sequence[Emblem]
