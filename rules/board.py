import random
from typing import Any, Dict, List, Optional, Sequence

from picaro.common.exceptions import IllegalMoveException
from picaro.common.hexmap.types import CubeCoordinate
from picaro.common.hexmap.utils import cube_linedraw

from .lib.deck import shuffle_discard
from .types.common import ResourceCard
from .types.store import Country, Game, Hex, ResourceDeck, Token


class BoardRules:
    @classmethod
    def best_routes(cls, start: str, ends: Sequence[str]) -> Dict[str, Sequence[str]]:
        start_hex = Hex.load(start)
        end_hexes = [Hex.load(e) for e in ends]
        start_cube = CubeCoordinate(x=start_hex.x, y=start_hex.y, z=start_hex.z)
        ret: Dict[str, Sequence[str]] = {}
        for eh in end_hexes:
            line_names: List[str] = []
            end_cube = CubeCoordinate(x=eh.x, y=eh.y, z=eh.z)
            line = cube_linedraw(start_cube, end_cube)
            for lc in line:
                line_hex = Hex.load_by_coordinate(lc)
                line_names.append(line_hex.name)
            if line_names and line_names[0] == start:
                line_names.pop(0)  # route doesn't include start hex
            ret[eh.name] = line_names
        return ret

    @classmethod
    def min_distance_from_entity(cls, entity_uuid: str, end: str) -> Optional[int]:
        vals = []
        for token in Token.load_all_by_entity(entity_uuid):
            vals.append(cls.distance(token.location, end))
        if not vals or any(v is None for v in vals):
            return None
        return min(vals)

    @classmethod
    def distance(cls, start: str, end: str) -> Optional[int]:
        start_hex = Hex.load(start)
        start_cube = CubeCoordinate(x=start_hex.x, y=start_hex.y, z=start_hex.z)
        end_hex = Hex.load(end)
        end_cube = CubeCoordinate(x=end_hex.x, y=end_hex.y, z=end_hex.z)
        return start_cube.distance(end_cube)

    @classmethod
    def get_single_token_hex(cls, uuid: str) -> Hex:
        token = Token.load_single_by_entity(uuid)
        return Hex.load(token.location)

    @classmethod
    def get_random_hex(cls) -> Hex:
        hexes = Hex.load_all()
        return random.choice(hexes)

    # finds hexes that are within x-y of any token of the entity, ordered by distance
    # (including the token's hex if min_distance is 0)
    @classmethod
    def find_entity_neighbors(
        cls, entity_uuid: str, min_distance: int, max_distance: int
    ) -> List[Hex]:
        neighbors: List[Tuple[int, Hex]] = []
        for token in Token.load_all_by_entity(entity_uuid):
            hx = Hex.load(token.location)
            start_cube = CubeCoordinate(x=hx.x, y=hx.y, z=hx.z)
            nghs = Hex.load_by_distance(start_cube, min_distance, max_distance)
            neighbors.extend(
                (start_cube.distance(CubeCoordinate(x=n.x, y=n.y, z=n.z)), n)
                for n in nghs
            )
        neighbors.sort(key=lambda ngh: (ngh[0], ngh[1].x, ngh[1].y, ngh[1].z))
        return [ngh[1] for ngh in neighbors]

    @classmethod
    def move_token_for_entity(
        cls, entity_uuid: str, hex_name: str, adjacent: bool
    ) -> None:
        with Token.load_single_by_entity_for_write(entity_uuid) as token:
            start_hex = Hex.load(token.location)
            end_hex = Hex.load(hex_name)
            if adjacent:
                start_cube = CubeCoordinate(x=start_hex.x, y=start_hex.y, z=start_hex.z)
                end_cube = CubeCoordinate(x=end_hex.x, y=end_hex.y, z=end_hex.z)
                if start_cube.distance(end_cube) != 1:
                    raise IllegalMoveException(
                        f"Hex {end_hex.name} is not adjacent to {start_hex.name}."
                    )
            token.location = end_hex.name

    @classmethod
    def draw_resource_card(cls, hex_name: str) -> ResourceCard:
        hx = Hex.load(hex_name)
        with ResourceDeck.load_for_write(hx.country) as deck:
            if not deck.cards:
                deck.cards = cls._make_resource_deck(hx.country)
            return deck.cards.pop(0)

    @classmethod
    def _make_resource_deck(cls, country_name: str) -> List[ResourceCard]:
        all_resources = set(Game.load().resources)

        if country_name == "Wild":
            cards = [ResourceCard(name="Nothing", type="nothing", value=0)] * 20
            for rs in all_resources:
                cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 1)
        else:
            country = Country.load(country_name)
            cards = [ResourceCard(name="Nothing", type="nothing", value=0)] * 8
            for rs in all_resources:
                if rs == country.resources[0]:
                    cards.extend([ResourceCard(name=f"{rs} x2", type=rs, value=2)] * 2)
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 4)
                elif rs == country.resources[1]:
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 3)
                else:
                    cards.extend([ResourceCard(name=f"{rs}", type=rs, value=1)] * 1)
        return shuffle_discard(cards)
