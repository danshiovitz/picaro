from dataclasses import dataclass
from enum import Enum, auto as enum_auto
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
    region: str


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
    NOTHING = enum_auto()
    GAIN_COINS = enum_auto()
    GAIN_XP = enum_auto()
    GAIN_REPUTATION = enum_auto()
    GAIN_HEALING = enum_auto()
    GAIN_RESOURCES = enum_auto()
    GAIN_QUEST = enum_auto()
    GAIN_TURNS = enum_auto()
    CHECK_FAILURE = enum_auto()
    LOSE_COINS = enum_auto()
    LOSE_REPUTATION = enum_auto()
    DAMAGE = enum_auto()
    LOSE_RESOURCES = enum_auto()
    DISRUPT_JOB = enum_auto()
    TRANSPORT = enum_auto()
    LOSE_TURNS = enum_auto()


@dataclass(frozen=True)
class Effect:
    type: EffectType
    rank: int
    param: Optional[Any]


class JobType(Enum):
    LACKEY = enum_auto()
    SOLO = enum_auto()
    CAPTAIN = enum_auto()
    KING = enum_auto()


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EffectType
    penalty: EffectType


class ChoiceType(Enum):
    NONE = enum_auto()
    REQUIRED = enum_auto()
    OPTIONAL = enum_auto()
    RANDOM = enum_auto()


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
class TableauCard:
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
    tableau: Sequence[TableauCard]
    encounters: Sequence[Encounter]
