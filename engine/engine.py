from typing import Dict, List, Tuple

from .board import Board
from .character import EncounterActions, EncounterOutcome, Party
from .exceptions import BadStateException, IllegalMoveException
from .types import Character, Token

class Engine:
    def __init__(self):
        self._board = Board()
        self._characters = Party()

    def get_board(self) -> Board:
        return self._board

    def add_character(self, character_name: str, player_id: int, location: str, job_name: str) -> None:
        self._characters.create_character(name=character_name, player_id=player_id, job_name=job_name, board=self._board, location=location)

    def get_character(self, character_name: str) -> Character:
        return self._characters.get_character(character_name, self._board)

    def start_season(self) -> None:
        self._characters.start_season(self._board)

    def do_job(self, character_name: str, card_id: int) -> None:
        self._characters.do_job(character_name, card_id, self._board)

    def do_travel(self, character_name: str, route: List[str]) -> None:
        self._characters.do_travel(character_name, route, self._board)

    def do_camp(self, character_name: str) -> None:
        self._characters.do_camp(character_name, self._board)

    def do_resolve_encounter(self, character_name: str, actions: EncounterActions) -> EncounterOutcome:
        return self._characters.resolve_encounter(character_name, actions, self._board)
