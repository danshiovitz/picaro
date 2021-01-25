from typing import Dict, List, Tuple

from .board import Board
from .character import Character, EncounterActions, EncounterOutcome
from .types import Token

class Engine:
    def __init__(self):
        self._board = Board()
        self._characters: Dict[str, Character] = {}

    def get_board(self) -> Board:
        return self._board

    def add_character(self, character_name: str, player_id: int, location: str, job_name: str) -> None:
        self._characters[character_name] = Character(name=character_name, player_id=player_id, job_name=job_name)
        self._board.add_token(Token(name=character_name, type="Character", location=location))

    def get_character(self, character_name: str) -> Character:
        ch = self._characters.get(character_name, None)
        if ch is None:
            raise Exception(f"No such character: {character_name}")
        return ch

    def find_character(self, character_name: str) -> Tuple[str, str]:
        return (self._board.get_token_location(character_name, False),
                self._board.get_token_location(character_name, True))

    def start_season(self) -> None:
        for ch in self._characters.values():
            ch.start_season(self._board)

    def do_start_encounter(self, character_name: str, card_id: int) -> None:
        ch = self._characters.get(character_name, None)
        if ch is None:
            raise Exception(f"No such character: {character_name}")
        ch.do_start_encounter(card_id, self._board)

    def do_resolve_encounter(self, character_name: str, actions: EncounterActions) -> EncounterOutcome:
        ch = self._characters.get(character_name, None)
        if ch is None:
            raise Exception(f"No such character: {character_name}")
        return ch.do_resolve_encounter(actions, self._board)

    def do_travel(self, character_name: str, route: List[str]) -> None:
        ch = self._characters.get(character_name, None)
        if ch is None:
            raise Exception(f"No such character: {character_name}")
        ch.do_travel(route, self._board)

    def do_camp(self, character_name: str) -> None:
        ch = self._characters.get(character_name, None)
        if ch is None:
            raise Exception(f"No such character: {character_name}")
        ch.do_camp(self._board)
