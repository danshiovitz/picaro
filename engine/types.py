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


class Hexmap(NamedTuple):
    hexes: List[Hex]
    tokens: List[Token]


class EncounterCheck(NamedTuple):
    skill: str
    difficuty: int


class FullCard(NamedTuple):
    name: str
    desc: str
    checks: List[EncounterCheck]
    age: int
    location: OffsetCoordinate
    signs: List[str]


class Tableau(NamedTuple):
    cards: List[FullCard]
    remaining_turns: int
    luck: int
    deck: List[FullCard]


class Character(NamedTuple):
    name: str
    player_id: Optional[int]
    tableau: Optional[Tableau]


class Player(NamedTuple):
    id: int
    name: str
