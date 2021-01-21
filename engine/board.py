import random
from typing import Dict, List, Optional

from picaro.common.hexmap.types import CubeCoordinate
from .deck import EncounterDeck
from .generate import generate_from_mini
from .types import EncounterPenalty, EncounterReward, Hex, TemplateCard, Token

class Board:
    def __init__(self) -> None:
        self.hexes = self._generate_hexes()
        self.by_cube = {CubeCoordinate.from_row_col(row=hx.coordinate.row, col=hx.coordinate.column): hx for hx in self.hexes.values()}
        self.hex_decks = {hx.name: self._make_deck_for_hex(hx) for hx in self.hexes.values()}
        self.tokens = {}

    def add_token(self, token: Token) -> None:
        if token.name in self.tokens:
            raise Exception(f"Token name {token.name} already in use")
        self.tokens[token.name] = token
        self.move_token(token.name, token.location)

    def move_token(self, token_name: str, to: str, adjacent: bool = False) -> None:
        if token_name not in self.tokens:
            raise Exception(f"No such token {token_name}")
        if to == "random":
            to = random.choice(list(self.hexes))
        if to != "Nowhere" and to not in self.hexes:
            raise Exception(f"Unknown location {to}")

        if adjacent:
            # neighbors includes current loc
            neighbors = [hh.name for hh in self.find_hexes_near_location(token_name, 0, 1)]
            if to not in neighbors:
                raise Exception("Location {to} isn't adjacent to {token_name}")

        self.tokens[token_name] = self.tokens[token_name]._replace(location=to)

    def find_hexes_near_location(self, location: str, min_distance: int, max_distance: int) -> List[Hex]:
        center = self.get_token_location(location, to_hex=True)
        center_cube = CubeCoordinate.from_row_col(row=self.hexes[center].coordinate.row, col=self.hexes[center].coordinate.column)
        filtered = [hh for cube, hh in self.by_cube.items() if min_distance <= center_cube.distance(cube) <= max_distance]
        if not filtered:
            raise Exception(f"No neighbors found for {location} at distance {min_distance}-{max_distance}")
        return filtered

    def get_token_location(self, token_name: str, to_hex: bool) -> str:
        if token_name not in self.tokens:
            raise Exception(f"No such token {token_name}")
        loc = self.tokens[token_name].location
        while loc not in self.hexes:
            if loc == "Nowhere":
                raise Exception("Token not on the board")
            elif loc not in self.tokens:
                raise Exception(f"Location {loc} not recognized")
            else:
                if not to_hex:
                    break
                loc = self.tokens[loc].location
        return loc

    def draw_hex_card(self, hex_name: str) -> None:
        if hex_name not in self.hex_decks:
            raise Exception(f"Hex {hex_name} not recognized")
        return self.hex_decks[hex_name].draw()

    def _generate_hexes(self) -> Dict[str, Hex]:
        minimap = [
            '^n::n::~',
            'n:n."..~',
            '"."."".~',
            '^n."".nn',
            '^.~~~~~~',
            '..""~..:',
            '""""^::n',
            '&&"^n:::',
        ]
        hexes = generate_from_mini(50, 50, minimap)
        return {hx.name: hx for hx in hexes}

    def _make_deck_for_hex(self, hx: Hex) -> EncounterDeck:
        # based on hx.terrain:
        base_skills = ["Desert Lore", "Desert Lore", "Endurance"]
        base_difficulty = 2
        cards = [
            TemplateCard("Oasis", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Sandstorm", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Desert Beast", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Extreme Heat", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Strange Constellations", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Mirage", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
        ]
        probs = [2, 2, 2, 2, 2, 2]
        while len(probs) < len(cards):
            probs.append(1)
        quantities = list(zip(cards, probs))
        return EncounterDeck(quantities, base_skills, base_difficulty)