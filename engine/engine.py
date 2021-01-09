from typing import List

from .engine_types import Character, Hexmap, Player, Token
from .generate import generate_from_mini

class Engine:
    def __init__(self):
        self._map = self._init_map()
        self._players: List[Player] = []
        self._characters: List[Character] = []

    def add_player(self, player_id: int, new_player_name: str) -> None:
        self._players.append(Player(id=103, name=new_player_name))

    def add_character(self, player_id: int, character_name: str) -> None:
        self._characters.append(Character(name=character_name, player_id=player_id))
        self._map.tokens.append(Token(name=character_name, type="Character", location="Nowhere"))

    def get_map(self, player_id: int) -> Hexmap:
        return self._map

    def _init_map(self) -> Hexmap:
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
        return Hexmap(hexes=generate_from_mini(50, 50, minimap), tokens=[])
