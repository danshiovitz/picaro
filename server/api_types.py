from typing import List, NamedTuple

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


class Hexmap(NamedTuple):
    hexes: List[Hex]
    tokens: List[Token]
