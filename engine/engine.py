from typing import Dict, List, Tuple

from .board import ActiveBoard
from .character import EncounterActions, EncounterOutcome, Party
from .exceptions import BadStateException, IllegalMoveException
from .storage import ConnectionManager, ConnectionWrapper
from .types import Board, Character, Optional, Token

class Engine:
    def __init__(self, db_path: Optional[str], json_path: str) -> None:
        ConnectionWrapper.initialize(db_path=db_path, json_path=json_path)
        self._board = ActiveBoard()
        self._characters = Party()

    def generate_hexes(self) -> None:
        with ConnectionManager():
            self._board.generate_hexes()

    def get_board(self) -> Board:
        with ConnectionManager():
            return self._board.get_snapshot()

    def add_character(self, character_name: str, player_id: int, location: str, job_name: str) -> None:
        with ConnectionManager():
            self._characters.create_character(name=character_name, player_id=player_id, job_name=job_name, board=self._board, location=location)

    def get_character(self, character_name: str) -> Character:
        with ConnectionManager():
            return self._characters.get_character(character_name, self._board)

    def start_season(self) -> None:
        with ConnectionManager():
            self._characters.start_season(self._board)

    def do_job(self, character_name: str, card_id: int) -> None:
        with ConnectionManager():
            self._characters.do_job(character_name, card_id, self._board)

    def do_travel(self, character_name: str, route: List[str]) -> None:
        with ConnectionManager():
            self._characters.do_travel(character_name, route, self._board)

    def do_camp(self, character_name: str) -> None:
        with ConnectionManager():
            self._characters.do_camp(character_name, self._board)

    def do_resolve_encounter(self, character_name: str, actions: EncounterActions) -> EncounterOutcome:
        with ConnectionManager():
            return self._characters.resolve_encounter(character_name, actions, self._board)
