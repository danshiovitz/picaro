from typing import List, NamedTuple


class Hex(NamedTuple):
    name: str
    row: int
    column: int
    terrain: str
    country: str


class Hexmap(NamedTuple):
    hexes: List[Hex]


Terrains = [
    "Forest", "Jungle", "Hills", "Mountains", "Plains", "Desert", "Water", "City", "Swamp", "Coastal", "Arctic",
]


Countries = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Theta", "Iota",
]
