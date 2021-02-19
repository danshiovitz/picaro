from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Sequence

from picaro.engine.types import (
    ChoiceType,
    TableauCard,
    Effect,
    Emblem,
    EncounterCheck,
    Hex,
    Token,
)


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
    luck: int
    speed: int
    tableau: Sequence[TableauCard]
    encounters: Sequence[Encounter]
    emblems: Sequence[Emblem]
