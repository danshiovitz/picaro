from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

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


class EncounterReward(Enum):
    COINS = 1
    XP = 2
    REPUTATION = 3
    HEALING = 4
    RESOURCES = 5
    QUEST = 6
    NOTHING = 7


class EncounterPenalty(Enum):
    COINS = 1
    REPUTATION = 2
    DAMAGE = 3
    RESOURCES = 4
    JOB = 5
    TRANSPORT = 6
    NOTHING = 7


class JobType(Enum):
    LACKEY = 1
    SOLO = 2
    CAPTAIN = 3
    KING = 4


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EncounterReward
    penalty: EncounterPenalty


@dataclass(frozen=True)
class TemplateCard:
    copies: int
    name: str
    desc: str
    skills: Sequence[str]
    rewards: Sequence[EncounterReward]
    penalties: Sequence[EncounterPenalty]


@dataclass(frozen=True)
class FullCard:
    id: int
    template: TemplateCard
    checks: Sequence[EncounterCheck]
    signs: Sequence[str]


@dataclass(frozen=True)
class DrawnCard:
    card: FullCard
    age: int
    location_name: str
