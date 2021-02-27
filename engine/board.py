import dataclasses
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from picaro.common.hexmap.types import CubeCoordinate

from .deck import load_deck
from .exceptions import BadStateException, IllegalMoveException
from .generate import generate_from_mini
from .snapshot import (
    Board as snapshot_Board,
    Hex as snapshot_Hex,
    Token as snapshot_Token,
)
from .storage import ObjectStorageBase
from .types import (
    Action,
    Country,
    Effect,
    EffectType,
    EncounterContextType,
    FullCard,
    ResourceCard,
    TemplateCard,
    Terrains,
)


TokenTypes = ["Character", "City", "Mine", "Other"]


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
        return snapshot_Board(hexes=snap_hexes, tokens=snap_tokens)

    def add_token(
        self,
        name: str,
        type: str,
        location: str,
        actions: Optional[Sequence[Action]] = None,
    ) -> None:
        found = False
        try:
            TokenStorage.load_by_name(name)
            found = True
        except IllegalMoveException:
            pass
        if found:
            raise IllegalMoveException(f"Token name {name} already in use")
        if type not in TokenTypes:
            raise Exception(f"Unknown token type {type}")
        if actions is None:
            actions = []
        TokenStorage.create(
            Token(name=name, type=type, location=location, actions=actions)
        )
        # this validates location so we don't have to:
        self.move_token(name, location)

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
            if new_hex.name not in nearby:
                raise IllegalMoveException(
                    f"Location {new_hex.name} isn't adjacent to {token_name}"
                )

        token = dataclasses.replace(token, location=to)
        TokenStorage.update(token)

    def get_token(self, token_name: str) -> snapshot_Token:
        return self._translate_token(TokenStorage.load_by_name(token_name), ["bogus"])

    def get_token_location(self, token_name: str) -> str:
        return TokenStorage.load_by_name(token_name).location

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
        center_hex = HexStorage.load_by_name(token.location)
        nearby = HexStorage.load_by_distance(
            center_hex.x, center_hex.y, center_hex.z, min_distance, max_distance
        )
        return [hx.name for hx in nearby]

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
            region=hx.region,
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
            hex_deck.deck = template_deck.semi_actualize(additional=[])
        template_card = hex_deck.deck.pop(0)
        card = template_deck.make_card(template_card, difficulty, context)
        HexDeckStorage.update(hex_deck)
        return card

    def draw_resource_card(self, hex_name: str) -> ResourceCard:
        hx = HexStorage.load_by_name(hex_name)
        resource_deck = ResourceDeckStorage.maybe_load_by_country_region(
            hx.country, hx.region
        )
        if resource_deck is None:
            resource_deck = ResourceDeck(country=hx.country, region=hx.region, deck=[])
            ResourceDeckStorage.insert(resource_deck)
        if not resource_deck.deck:
            resource_deck.deck = self._make_resource_deck(hx.country, hx.region)
        card = resource_deck.deck.pop(0)
        ResourceDeckStorage.update(resource_deck)
        return card

    def _make_resource_deck(self, country: str, region: str) -> List[ResourceCard]:
        countries = CountryStorage.load()
        resources = set()
        for c in countries:
            resources |= set(c.resources)

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

    def generate_map(self) -> None:
        all_hexes = HexStorage.load()
        if all_hexes:
            raise Exception("Can't generate, hexes already exist")

        minimap = [
            "^n::n::~",
            'n:n."..~',
            '"."."".~',
            '^n."".nn',
            "^.~~~~~~",
            '.."~~..:',
            '""""^::n',
            '&&"^n:::',
        ]
        hexes, countries, mines = generate_from_mini(50, 50, minimap)

        CountryStorage.insert_all(countries)

        # translate these into storage format:
        def trans(hx: snapshot_Hex) -> Hex:
            cube = CubeCoordinate.from_row_col(
                row=hx.coordinate.row, col=hx.coordinate.column
            )
            return Hex(
                name=hx.name,
                terrain=hx.terrain,
                country=hx.country,
                region=hx.region,
                x=cube.x,
                y=cube.y,
                z=cube.z,
                danger=hx.danger,
            )

        HexStorage.insert([trans(hx) for hx in hexes])

        # using http://www.dungeoneering.net/d100-list-fantasy-town-names/ as a placeholder
        # for now
        city_names = [
            "Aerilon",
            "Aquarin",
            "Aramoor",
            "Azmar",
            "Beggar's Hole",
            "Black Hollow",
            "Blue Field",
            "Briar Glen",
            "Brickelwhyte",
            "Broken Shield",
            "Boatwright",
            "Bullmar",
            "Carran",
            "City of Fire",
            "Coalfell",
            "Cullfield",
            "Darkwell",
            "Deathfall",
            "Doonatel",
            "Dry Gulch",
            "Easthaven",
            "Ecrin",
            "Erast",
            "Far Water",
            "Firebend",
            "Fool's March",
            "Frostford",
            "Goldcrest",
            "Goldenleaf",
            "Greenflower",
            "Garen's Well",
            "Haran",
            "Hillfar",
            "Hogsfeet",
            "Hollyhead",
            "Hull",
            "Hwen",
            "Icemeet",
            "Ironforge",
            "Irragin",
        ]
        random.shuffle(city_names)

        mine_set = {m for m in mines}
        mine_rs = {c.name: c.resources[0] for c in countries}

        for hx in hexes:
            if hx.terrain == "City":
                actions = [
                    Action(
                        name="Trade",
                        cost=[Effect(type=EffectType.MODIFY_RESOURCES, value=-1)],
                        benefit=[Effect(type=EffectType.MODIFY_COINS, value=5)],
                    ),
                ]
                token = Token(
                    name=city_names.pop(0),
                    type="City",
                    location=hx.name,
                    actions=actions,
                )
                TokenStorage.create(token)

            if hx.name in mine_set:
                actions = [
                    Action(
                        name=f"Gather {mine_rs[hx.country]}",
                        cost=[Effect(type=EffectType.MODIFY_ACTION, value=-1)],
                        benefit=[
                            Effect(
                                type=EffectType.MODIFY_RESOURCES,
                                param=mine_rs[hx.country],
                                value=1,
                            )
                        ],
                    ),
                ]
                token = Token(
                    name=f"{mine_rs[hx.country]} Source",
                    type="Mine",
                    location=hx.name,
                    actions=actions,
                )
                TokenStorage.create(token)


# this one is not frozen and not exposed externally
@dataclass
class Hex:
    name: str
    terrain: str
    country: str
    region: str
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
    region: str
    deck: List[ResourceCard]


@dataclass
class Token:
    name: str
    type: str
    location: str
    actions: List[Action]


class HexStorage(ObjectStorageBase[Hex]):
    TABLE_NAME = "hex"
    TYPE = Hex
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
    TYPE = HexDeck
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

    @classmethod
    def insert_initial_data(cls, _json_dir: str) -> List[HexDeck]:
        vals = [HexDeck(name=t, deck=[]) for t in Terrains]
        cls._insert_helper(vals)


class ResourceDeckStorage(ObjectStorageBase[ResourceDeck]):
    TABLE_NAME = "resource_deck"
    TYPE = ResourceDeck
    PRIMARY_KEYS = {"country", "region"}

    @classmethod
    def load(cls) -> List[ResourceDeck]:
        return cls._select_helper([], {})

    @classmethod
    def maybe_load_by_country_region(
        cls, country: str, region: str
    ) -> Optional[ResourceDeck]:
        decks = cls._select_helper(
            ["country = :country", "region = :region"],
            {"country": country, "region": region},
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

    @classmethod
    def insert_initial_data(cls, _json_dir: str) -> List[ResourceDeck]:
        return []


class TokenStorage(ObjectStorageBase[Token]):
    TABLE_NAME = "token"
    TYPE = Token
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
    def update(cls, token: Token) -> Token:
        cls._update_helper(token)
        return token


class CountryStorage(ObjectStorageBase[Country]):
    TABLE_NAME = "country"
    TYPE = Country
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
