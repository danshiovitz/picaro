from enum import Enum
from typing import NamedTuple, Optional, Sequence

from picaro.common.hexmap.types import OffsetCoordinate


Terrains = [
    "Forest", "Jungle", "Hills", "Mountains", "Plains", "Desert", "Water", "City", "Swamp", "Coastal", "Arctic",
]


Countries = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Theta", "Iota",
]


class Hex(NamedTuple):
    name: str
    coordinate: OffsetCoordinate
    terrain: str
    country: str


TokenTypes = ["Character", "Other"]


class Token(NamedTuple):
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


class EncounterCheck(NamedTuple):
    skill: str
    target_number: int
    reward: EncounterReward
    penalty: EncounterPenalty


class TemplateCard(NamedTuple):
    copies: int
    name: str
    desc: str
    skills: Sequence[str]
    rewards: Sequence[EncounterReward]
    penalties: Sequence[EncounterPenalty]


class FullCard(NamedTuple):
    id: int
    template: TemplateCard
    checks: Sequence[EncounterCheck]
    signs: Sequence[str]


class DrawnCard(NamedTuple):
    card: FullCard
    age: int
    location_name: str
