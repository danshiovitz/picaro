from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence

from picaro.common.hexmap.types import OffsetCoordinate


Terrains = [
    "Forest", "Jungle", "Hills", "Mountains", "Plains", "Desert", "Water", "City", "Swamp", "Coastal", "Arctic",
]


Countries = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Theta", "Iota",
]


@dataclass(frozen=True)
class Hex:
    name: str
    coordinate: OffsetCoordinate
    terrain: str
    country: str


TokenTypes = ["Character", "Other"]


@dataclass(frozen=True)
class Token:
    name: str
    type: str
    location: str


@dataclass(frozen=True)
class Board:
    hexes: Sequence[Hex]
    tokens: Sequence[Token]


class EffectType(Enum):
    NOTHING = 0
    GAIN_COINS = 1
    GAIN_XP = 2
    GAIN_REPUTATION = 3
    GAIN_HEALING = 4
    GAIN_RESOURCES = 5
    GAIN_QUEST = 6
    CHECK_FAILURE = 7
    LOSE_COINS = 20
    LOSE_REPUTATION = 21
    DAMAGE = 22
    LOSE_RESOURCES = 23
    DISRUPT_JOB = 24
    TRANSPORT = 25


@dataclass(frozen=True)
class Effect:
    type: EffectType
    rank: int
    param: Optional[Any]


class JobType(Enum):
    LACKEY = 1
    SOLO = 2
    CAPTAIN = 3
    KING = 4


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EffectType
    penalty: EffectType


class ChoiceType(Enum):
    NONE = 0
    REQUIRED = 1
    OPTIONAL = 2
    RANDOM = 3


@dataclass(frozen=True)
class TemplateCard:
    copies: int
    name: str
    desc: str
    skills: Sequence[str]
    rewards: Sequence[EffectType]
    penalties: Sequence[EffectType]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]


@dataclass(frozen=True)
class FullCard:
    id: str
    name: str
    desc: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
    signs: Sequence[str]


@dataclass(frozen=True)
class DrawnCard:
    card: FullCard
    age: int
    location_name: str


@dataclass(frozen=True)
class Encounter:
    card: FullCard
    rolls: Sequence[int]


@dataclass(frozen=True)
class Character:
    name: str
    player_id: str
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
    tableau: Sequence[DrawnCard]
    encounters: Sequence[Encounter]
