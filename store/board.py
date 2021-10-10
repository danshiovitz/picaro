from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from picaro.common.exceptions import IllegalMoveException
from picaro.common.hexmap.types import CubeCoordinate

from .base import StandardStorage, StandardWrapper
from .common_types import ResourceCard, TemplateCard


@dataclass
class HexStorage(StandardStorage["HexStorage"]):
    TABLE_NAME = "hex"

    name: str
    terrain: str
    country: str
    x: int
    y: int
    z: int
    danger: int

    @classmethod
    def load_by_coordinate(cls, x: int, y: int, z: int) -> "HexStorage":
        hexes = cls._select_helper(
            ["x = :x", "y = :y", "z = :z"], {"x": x, "y": y, "z": z}
        )
        if not hexes:
            raise IllegalMoveException(f"No such hex: {x},{y},{z}")
        return hexes[0]

    @classmethod
    def load_by_distance(
        cls, c_x: int, c_y: int, c_z: int, min_distance: int, max_distance: int
    ) -> List["HexStorage"]:
        dist_clause = "((abs(:c_x - x) + abs(:c_y - y) + abs(:c_z - z)) / 2) BETWEEN :min_distance AND :max_distance"
        return cls._select_helper(
            [dist_clause],
            {
                "c_x": c_x,
                "c_y": c_y,
                "c_z": c_z,
                "min_distance": min_distance,
                "max_distance": max_distance,
            },
        )


class Hex(StandardWrapper[HexStorage]):
    @classmethod
    def load_by_coordinate(cls, cube: CubeCoordinate) -> "Hex":
        data = HexStorage.load_by_coordinate(cube.x, cube.y, cube.z)
        return Hex(data)

    @classmethod
    def load_by_distance(
        cls, cube: CubeCoordinate, min_distance: int, max_distance: int
    ) -> List["Hex"]:
        data_lst = HexStorage.load_by_distance(
            cube.x, cube.y, cube.z, min_distance, max_distance
        )
        return [Hex(d) for d in data_lst]


@dataclass
class TokenStorage(StandardStorage["TokenStorage"]):
    TABLE_NAME = "token"

    uuid: str
    entity: str
    location: str

    @classmethod
    def load_by_entity(cls, entity: str) -> List["TokenStorage"]:
        return cls._select_helper(["entity = :entity"], {"entity": entity})


class Token(StandardWrapper[TokenStorage]):
    @classmethod
    def load_all_by_entity(cls, entity: str) -> List["Token"]:
        return [Token(d) for d in TokenStorage.load_by_entity(entity)]

    @classmethod
    def load_single_by_entity(cls, entity: str) -> "Token":
        tokens = [Token(d) for d in TokenStorage.load_by_entity(entity)]
        if len(tokens) != 1:
            raise IllegalMoveException(f"Expected single token for {entity}")
        return tokens[0]

    @classmethod
    def load_single_by_entity_for_write(cls, entity: str) -> "Token":
        tokens = [Token(d, can_write=True) for d in TokenStorage.load_by_entity(entity)]
        if len(tokens) != 1:
            raise IllegalMoveException(f"Expected single token for {entity}")
        return tokens[0]


@dataclass
class CountryStorage(StandardStorage["CountryStorage"]):
    TABLE_NAME = "country"

    uuid: str
    name: str
    capitol_hex: str
    resources: List[str]

    @classmethod
    def load_by_name(cls, name: str) -> "CountryStorage":
        countries = cls._select_helper(["name = :name"], {"name": name})
        if not countries:
            raise IllegalMoveException(f"No such country: {name}")
        return countries[0]


class Country(StandardWrapper[CountryStorage]):
    @classmethod
    def load(cls, name: str) -> "Country":
        data = CountryStorage.load_by_name(name)
        return Country(data)

    @classmethod
    def load_for_write(cls, name: str) -> "Country":
        data = CountryStorage.load_by_name(name)
        return Country(data, can_write=True)


@dataclass
class HexDeckStorage(StandardStorage["HexDeckStorage"]):
    TABLE_NAME = "hex_deck"

    # Decks are per-hex-type, so deck name is the terrain name
    name: str
    cards: Sequence[TemplateCard]


class HexDeck(StandardWrapper[HexDeckStorage]):
    pass


@dataclass
class ResourceDeckStorage(StandardStorage["ResourceDeckStorage"]):
    TABLE_NAME = "resource_deck"

    # Decks are per-country, so deck name is the country name
    name: str
    cards: Sequence[ResourceCard]


class ResourceDeck(StandardWrapper[ResourceDeckStorage]):
    pass
