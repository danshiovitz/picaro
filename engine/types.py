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


class EncounterCheck(NamedTuple):
    skill: str
    target_number: int


class TemplateCard(NamedTuple):
    name: str
    desc: str
    skills: List[str]


class FullCard(NamedTuple):
    id: int
    template: TemplateCard
    checks: List[EncounterCheck]
    signs: List[str]


class DrawnCard(NamedTuple):
    card: FullCard
    age: int
    location: OffsetCoordinate
