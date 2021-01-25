from enum import Enum
from typing import List, NamedTuple, Optional

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


class EncounterCheck(NamedTuple):
    skill: str
    target_number: int
    reward: EncounterReward
    penalty: EncounterPenalty


class TemplateCard(NamedTuple):
    copies: int
    name: str
    desc: str
    skills: List[str]
    rewards: List[EncounterReward]
    penalties: List[EncounterPenalty]


class FullCard(NamedTuple):
    id: int
    template: TemplateCard
    checks: List[EncounterCheck]
    signs: List[str]


class DrawnCard(NamedTuple):
    card: FullCard
    age: int
    location_name: str
