import dataclasses
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from picaro.common.hexmap.types import CubeCoordinate, OffsetCoordinate

from .deck import make_card, load_deck, semi_actualize_deck
from .exceptions import BadStateException, IllegalMoveException
from .game import load_game
from .snapshot import (
    Board as snapshot_Board,
    Hex as snapshot_Hex,
    Token as snapshot_Token,
)
from .storage import ObjectStorageBase
from .types import (
    Action,
    Choice,
    Choices,
    Country,
    Effect,
    EffectType,
    EncounterContextType,
    EntityType,
    Record,
    FullCard,
    ResourceCard,
    TemplateCard,
    Terrains,
    make_id,
)


# This one isn't serialized at all, it owns no data directly
class ActiveBoard:
    NOWHERE = "Nowhere"

    def get_snapshot(self, token_name: str) -> snapshot_Board:
        start_hex = self.get_token_location(token_name)
        hexes = HexStorage.load()
        snap_hexes = tuple(self._translate_hex(hx) for hx in hexes)
        tokens = TokenStorage.load()
        routes = self.best_routes(start_hex, [t.location for t in tokens], hexes=hexes)
        snap_tokens = tuple(
            self._translate_token(tok, routes[tok.location]) for tok in tokens
        )
        countries = CountryStorage.load()
        snap_resources = tuple(load_game().resources)

        return snapshot_Board(
            hexes=snap_hexes, tokens=snap_tokens, resources=snap_resources
        )

    def add_token(
        self,
        name: str,
        type: EntityType,
        location: str,
        actions: Optional[Sequence[Action]],
        records: List[Record],
    ) -> None:
        found = False
        try:
            TokenStorage.load_by_name(name)
            found = True
        except IllegalMoveException:
            pass
        if found:
            raise IllegalMoveException(f"Token name {name} already in use")
        if actions is None:
            actions = []
        TokenStorage.create(
            Token(name=name, type=type, location=location, actions=actions)
        )
        # this validates location so we don't have to:
        self.move_token(
            name, location, adjacent=False, comments=["Token created"], records=records
        )

    def remove_token(self, token_name: str) -> None:
        token = TokenStorage.load_by_name(token_name)
        TokenStorage.delete_by_name(token_name)

    def move_token(
        self,
        token_name: str,
        to: str,
        adjacent: bool,
        comments: List[str],
        records: List[Record],
    ) -> None:
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

        old_hex = token.location
        if adjacent and token.location != self.NOWHERE:
            nearby = self.find_hexes_near_token(token_name, 0, 1)
            if new_hex.name not in nearby:
                raise IllegalMoveException(
                    f"Location {new_hex.name} isn't adjacent to {token_name}"
                )

        token = dataclasses.replace(token, location=to)
        TokenStorage.update(token)
        records.append(
            Record(
                make_id(),
                token.type,
                token.name,
                EffectType.MODIFY_LOCATION,
                None,
                old_hex,
                new_hex.name,
                comments,
            )
        )

    def get_token(self, token_name: str) -> snapshot_Token:
        return self._translate_token(TokenStorage.load_by_name(token_name), ["bogus"])

    def get_token_location(self, token_name: str) -> str:
        return TokenStorage.load_by_name(token_name).location

    def get_token_action(
        self, token_name: str, action_name: str
    ) -> Tuple[Action, EntityType, str]:
        token = TokenStorage.load_by_name(token_name)
        for action in token.actions:
            if action.name == action_name:
                return (action, token.type, token.name)
        raise BadStateException(f"No such action {action_name} on token {token_name}.")

    def _translate_token(self, token: "Token", route: Sequence[str]) -> snapshot_Token:
        return snapshot_Token(
            name=token.name,
            type=token.type,
            location=token.location,
            actions=tuple(token.actions),
            route=route,
        )

    def get_hex(self, location: str) -> snapshot_Hex:
        return self._translate_hex(HexStorage.load_by_name(location))

    def find_hexes_near_token(
        self, token_name: str, min_distance: int, max_distance: int
    ) -> List[str]:
        token = TokenStorage.load_by_name(token_name)
        if token.location == self.NOWHERE:
            return []
        return self.find_hexes_near_hex(token.location, min_distance, max_distance)

    def find_hexes_near_hex(
        self, hex_name: str, min_distance: int, max_distance: int
    ) -> List[str]:
        center_hex = HexStorage.load_by_name(hex_name)
        nearby = HexStorage.load_by_distance(
            center_hex.x, center_hex.y, center_hex.z, min_distance, max_distance
        )
        return [hx.name for hx in nearby]

    def random_hex_near_hex(
        self, hex_name: str, min_distance: int, max_distance: int
    ) -> str:
        center_hex = HexStorage.load_by_name(hex_name)
        nearby = HexStorage.load_by_distance(
            center_hex.x, center_hex.y, center_hex.z, min_distance, max_distance
        )
        return random.choice([hx.name for hx in nearby])

    def best_routes(
        self,
        start_hex: str,
        finish_hexes: List[str],
        hexes: Optional[List["Hex"]] = None,
    ) -> Dict[str, List[str]]:
        names = {hx.name: hx for hx in (hexes if hexes else HexStorage.load())}
        assert start_hex in names
        assert all(hxn in names for hxn in finish_hexes)
        ngh_map = self._calc_neighbors(names.values())

        targets = {hxn for hxn in finish_hexes}
        seen: Set[str] = set()
        pool = [(start_hex, [])]
        ret = {}
        while pool:
            cur, route = pool.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            if cur in targets:
                ret[cur] = route
                if len(ret) == len(targets):
                    return ret
            for ngh in ngh_map[cur]:
                pool.append((ngh, route + [ngh]))
        raise Exception(
            f"Couldn't find routes from {start_hex} to {finish_hexes} - {ret}"
        )

    def _calc_neighbors(self, hexes: Sequence["Hex"]) -> Dict[str, List[str]]:
        reverse = {(hx.x, hx.y, hx.z): hx.name for hx in hexes}
        ret = {}
        for hx in hexes:
            ngh_vals = [
                (hx.x + 1, hx.y - 1, hx.z + 0),
                (hx.x + 1, hx.y + 0, hx.z - 1),
                (hx.x + 0, hx.y + 1, hx.z - 1),
                (hx.x - 1, hx.y + 1, hx.z + 0),
                (hx.x - 1, hx.y + 0, hx.z + 1),
                (hx.x + 0, hx.y - 1, hx.z + 1),
            ]
            ret[hx.name] = [reverse[ngh] for ngh in ngh_vals if ngh in reverse]
        return ret

    def _translate_hex(self, hx: "Hex") -> snapshot_Hex:
        return snapshot_Hex(
            name=hx.name,
            terrain=hx.terrain,
            country=hx.country,
            coordinate=CubeCoordinate(x=hx.x, y=hx.y, z=hx.z).to_offset(),
            danger=hx.danger,
        )

    def draw_hex_card(self, hex_name: str, context: EncounterContextType) -> FullCard:
        hx = HexStorage.load_by_name(hex_name)
        deck_name = "Desert"
        difficulty = hx.danger + 1
        hex_deck = HexDeckStorage.load_by_name(deck_name)
        template_deck = load_deck(deck_name)
        if not hex_deck.deck:
            hex_deck.deck = semi_actualize_deck(template_deck, additional=[])
        template_card = hex_deck.deck.pop(0)
        card = make_card(template_deck, template_card, difficulty, context)
        HexDeckStorage.update(hex_deck)
        return card

    def draw_resource_card(self, hex_name: str) -> ResourceCard:
        hx = HexStorage.load_by_name(hex_name)
        resource_deck = ResourceDeckStorage.maybe_load_by_country(hx.country)
        if resource_deck is None:
            resource_deck = ResourceDeck(country=hx.country, deck=[])
            ResourceDeckStorage.insert(resource_deck)
        if not resource_deck.deck:
            resource_deck.deck = self._make_resource_deck(hx.country)
        card = resource_deck.deck.pop(0)
        ResourceDeckStorage.update(resource_deck)
        return card

    def _make_resource_deck(self, country: str) -> List[ResourceCard]:
        countries = CountryStorage.load()
        resources = set(load_game().resources)

        if country == "Wild":
            cards = [ResourceCard(name="Nothing", type="nothing", value=0)] * 20
            for rs in resources:
                cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 1)
        else:
            cur = [c for c in countries if c.name == country][0]
            cards = [ResourceCard(name="Nothing", type="nothing", value=0)] * 8
            for rs in resources:
                if rs == cur.resources[0]:
                    cards.extend([ResourceCard(name=f"{rs} x2", type=rs, value=2)] * 2)
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 4)
                elif rs == cur.resources[1]:
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 3)
                else:
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 1)
        random.shuffle(cards)
        for _ in range((len(cards) // 10) + 1):
            cards.pop()
        return cards


# since it has no state, this doesn't actually have to hit db currently
def load_board() -> ActiveBoard:
    return ActiveBoard()


def create_board(
    hexes: List[snapshot_Hex],
    tokens: List[snapshot_Token],
    countries: List[Country],
) -> None:
    HexStorage.insert([_translate_from_snapshot_hex(hx) for hx in hexes])
    TokenStorage.insert_all([_translate_from_snapshot_token(tk) for tk in tokens])
    CountryStorage.insert_all(countries)

    for t in Terrains:
        HexDeckStorage.insert(HexDeck(name=t, deck=[]))


def _translate_from_snapshot_hex(hx: snapshot_Hex) -> "Hex":
    cube = CubeCoordinate.from_row_col(row=hx.coordinate.row, col=hx.coordinate.column)
    return Hex(
        name=hx.name,
        terrain=hx.terrain,
        country=hx.country,
        x=cube.x,
        y=cube.y,
        z=cube.z,
        danger=hx.danger,
    )


def _translate_from_snapshot_token(token: snapshot_Token) -> "Token":
    return Token(
        name=token.name,
        type=token.type,
        location=token.location,
        actions=token.actions,
    )


# this one is not frozen and not exposed externally
@dataclass
class Hex:
    name: str
    terrain: str
    country: str
    x: int
    y: int
    z: int
    danger: int


# The idea here is for hexes we hold the cards in a "semi-actualized" form where
# we have the template deck shared across multiple hexes (so you don't see a sandstorm
# in multiple hexes in a row most of the time), but the cards don't get fully actualized
# until drawn (because we don't know whether the hex is a more or less dangerous one, or
# whether this is being drawn in the context of a job or travel)
@dataclass
class HexDeck:
    name: str  # note this name is assumed to match the template deck
    deck: List[TemplateCard]


@dataclass
class ResourceDeck:
    country: str
    deck: List[ResourceCard]


@dataclass
class Token:
    name: str
    type: EntityType
    location: str
    actions: List[Action]


class HexStorage(ObjectStorageBase[Hex]):
    TABLE_NAME = "hex"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Hex]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> Hex:
        hexes = cls._select_helper(["name = :name"], {"name": name})
        if not hexes:
            raise IllegalMoveException(f"No such hex: {name}")
        return hexes[0]

    @classmethod
    def load_by_coordinate(cls, x: int, y: int, z: int) -> Hex:
        hexes = cls._select_helper(
            ["x = :x", "y = :y", "z = :z"], {"x": x, "y": y, "z": z}
        )
        if not hexes:
            raise IllegalMoveException(f"No such hex: {x},{y},{z}")
        return hexes[0]

    @classmethod
    def load_by_distance(
        cls, c_x: int, c_y: int, c_z: int, min_distance: int, max_distance: int
    ) -> List[Hex]:
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

    @classmethod
    def insert(cls, hexes: List[Hex]) -> None:
        cls._insert_helper(hexes)

    @classmethod
    def update(cls, hx: Hex) -> Hex:
        cls._update_helper(hx)
        return hx


class HexDeckStorage(ObjectStorageBase[HexDeck]):
    TABLE_NAME = "hex_deck"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[HexDeck]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> HexDeck:
        decks = cls._select_helper(["name = :name"], {"name": name})
        if not decks:
            raise IllegalMoveException(f"No such deck: {name}")
        return decks[0]

    @classmethod
    def insert(cls, deck: HexDeck) -> None:
        cls._insert_helper([deck])

    @classmethod
    def update(cls, deck: HexDeck) -> None:
        cls._update_helper(deck)


class ResourceDeckStorage(ObjectStorageBase[ResourceDeck]):
    TABLE_NAME = "resource_deck"
    PRIMARY_KEYS = {"country"}

    @classmethod
    def load(cls) -> List[ResourceDeck]:
        return cls._select_helper([], {})

    @classmethod
    def maybe_load_by_country(cls, country: str) -> Optional[ResourceDeck]:
        decks = cls._select_helper(
            ["country = :country"],
            {"country": country},
        )
        if not decks:
            return None
        return decks[0]

    @classmethod
    def insert(cls, deck: ResourceDeck) -> None:
        cls._insert_helper([deck])

    @classmethod
    def update(cls, deck: ResourceDeck) -> None:
        cls._update_helper(deck)


class TokenStorage(ObjectStorageBase[Token]):
    TABLE_NAME = "token"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Token]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> Token:
        tokens = cls._select_helper(["name = :name"], {"name": name})
        if not tokens:
            raise IllegalMoveException(f"No such token: {name}")
        return tokens[0]

    @classmethod
    def load_by_location(cls, location: str) -> List[Token]:
        return cls._select_helper(["location = :location"], {"location": location})

    @classmethod
    def create(cls, token: Token) -> Token:
        cls._insert_helper([token])
        return token

    @classmethod
    def insert_all(cls, tokens: List[Token]) -> None:
        cls._insert_helper(tokens)

    @classmethod
    def update(cls, token: Token) -> Token:
        cls._update_helper(token)
        return token

    @classmethod
    def delete_by_name(cls, name: str) -> None:
        cls._delete_helper(["name = :name"], {"name": name})


class CountryStorage(ObjectStorageBase[Country]):
    TABLE_NAME = "country"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Country]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> Country:
        countries = cls._select_helper(["name = :name"], {"name": name})
        if not countries:
            raise IllegalMoveException(f"No such country: {name}")
        return countries[0]

    @classmethod
    def insert_all(cls, countries: List[Country]) -> None:
        cls._insert_helper(countries)
