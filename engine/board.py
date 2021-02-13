import dataclasses
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from picaro.common.hexmap.types import CubeCoordinate
from .deck import EncounterDeck, load_deck
from .exceptions import BadStateException, IllegalMoveException
from .generate import generate_from_mini
from .storage import ObjectStorageBase
from .types import FullCard, Hex as HexSnapshot, Token

# this one is not frozen and not exposed externally
@dataclass
class Hex:
    name: str
    terrain: str
    country: str
    x: int
    y: int
    z: int
    deck: List[FullCard]


# This one isn't serialized at all, it owns no data directly
class Board:
    NOWHERE = "Nowhere"

    def add_token(self, token: Token) -> None:
        names = {t.name for t in TokenStorage.load()}
        if token.name in names:
            raise IllegalMoveException(f"Token name {token.name} already in use")
        TokenStorage.create(token)
        self.move_token(token.name, token.location)

    def move_token(self, token_name: str, to: str, adjacent: bool = False) -> None:
        token = TokenStorage.load_by_name(token_name)
        if to == self.NOWHERE:
            token = dataclasses.replace(token, location=self.NOWHERE)
            TokenStorage.update(token)
            return

        if to == "random":
            all_hexes = HexStorage.load()
            to = random.choice(all_hexes).name

        # validate the new location
        new_hex = HexStorage.load_by_name(to)

        if adjacent and token.location != self.NOWHERE:
            nearby = self.find_hexes_near_token(token_name, 0, 1)
            print(f"nearby: {nearby}")
            if new_hex.name not in nearby:
                raise IllegalMoveException(f"Location {new_hex.name} isn't adjacent to {token_name}")

        token = dataclasses.replace(token, location=to)
        TokenStorage.update(token)

    def get_token(self, token_name: str) -> Token:
        return TokenStorage.load_by_name(token_name)

    def get_all_tokens(self) -> List[Token]:
        return TokenStorage.load()

    def find_hexes_near_token(self, token_name: str, min_distance: int, max_distance: int) -> List[str]:
        token = TokenStorage.load_by_name(token_name)
        if token.location == self.NOWHERE:
            return []
        center_hex = HexStorage.load_by_name(token.location)
        nearby = HexStorage.load_by_distance(center_hex.x, center_hex.y, center_hex.z, min_distance, max_distance)
        return [hx.name for hx in nearby]

    def get_hex(self, location: str) -> HexSnapshot:
        return self._translate_hex(HexStorage.load_by_name(location))

    def get_all_hexes(self) -> List[HexSnapshot]:
        return [self._translate_hex(hx) for hx in HexStorage.load()]

    def _translate_hex(self, hx: Hex) -> HexSnapshot:
        return HexSnapshot(
            name=hx.name,
            terrain=hx.terrain,
            country=hx.country,
            coordinate=CubeCoordinate(x=hx.x, y=hx.y, z=hx.z).to_offset()
        )

    def draw_hex_card(self, hex_name: str) -> FullCard:
        hx = HexStorage.load_by_name(hex_name)
        if not hx.deck:
            hx.deck = self._make_deck_for_hex(hx)
        card = hx.deck.pop(0)
        HexStorage.update(hx)
        return card

    def _make_deck_for_hex(self, hx: Hex) -> List[FullCard]:
        deck_name = "Desert"
        difficulty = 3
        template_deck = load_deck(deck_name)
        return template_deck.actualize(difficulty, additional=[])

    def generate_hexes(self) -> None:
        all_hexes = HexStorage.load()
        if all_hexes:
            raise Exception("Can't generate, hexes already exist")

        minimap = [
            '^n::n::~',
            'n:n."..~',
            '"."."".~',
            '^n."".nn',
            '^.~~~~~~',
            '.."~~..:',
            '""""^::n',
            '&&"^n:::',
        ]
        hexes = generate_from_mini(50, 50, minimap)

        # translate these into storage format:
        def trans(hx: HexSnapshot) -> Hex:
            cube = CubeCoordinate.from_row_col(row=hx.coordinate.row, col=hx.coordinate.column)
            return Hex(
                name=hx.name,
                terrain=hx.terrain,
                country=hx.country,
                x=cube.x,
                y=cube.y,
                z=cube.z,
                deck=[],
            )

        HexStorage.insert([trans(hx) for hx in hexes])


class HexStorage(ObjectStorageBase[Hex]):
    TABLE_NAME = "hex"
    TYPE = Hex
    PRIMARY_KEY = "name"

    @classmethod
    def load(cls) -> List[Hex]:
        return cls._select_helper([], {}, active_conn=None)

    @classmethod
    def load_by_name(cls, name: str) -> Hex:
        hexes = cls._select_helper(["name = :name"], {"name": name}, active_conn=None)
        if not hexes:
            raise Exception(f"No such hex: {name}")
        return hexes[0]

    @classmethod
    def load_by_distance(cls, c_x: int, c_y: int, c_z: int, min_distance: int, max_distance: int) -> List[Hex]:
        dist_clause = "((abs(:c_x - x) + abs(:c_y - y) + abs(:c_z - z)) / 2) BETWEEN :min_distance AND :max_distance"
        return cls._select_helper([dist_clause], {"c_x": c_x, "c_y": c_y, "c_z": c_z, "min_distance": min_distance, "max_distance": max_distance}, active_conn=None)

    @classmethod
    def insert(cls, hexes: List[Hex]) -> None:
        cls._insert_helper(hexes, active_conn=None)

    @classmethod
    def update(cls, hex: Hex) -> Hex:
        cls._update_helper(hex, active_conn=None)
        return hex


class TokenStorage(ObjectStorageBase[Token]):
    TABLE_NAME = "token"
    TYPE = Token
    PRIMARY_KEY = "name"

    @classmethod
    def load(cls) -> List[Token]:
        return cls._select_helper([], {}, active_conn=None)

    @classmethod
    def load_by_name(cls, name: str) -> Token:
        tokens = cls._select_helper(["name = :name"], {"name": name}, active_conn=None)
        if not tokens:
            raise Exception(f"No such token: {name}")
        return tokens[0]

    @classmethod
    def load_by_location(cls, location: str) -> List[Token]:
        return cls._select_helper(["location = :location"], {"location": location}, active_conn=None)

    @classmethod
    def create(cls, token: Token) -> Token:
        cls._insert_helper([token], active_conn=None)
        return token

    @classmethod
    def update(cls, token: Token) -> Token:
        cls._update_helper(token, active_conn=None)
        return token
