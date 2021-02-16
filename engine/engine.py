from pathlib import Path
from typing import Sequence

from .board import ActiveBoard
from .character import Party
from .exceptions import BadStateException, IllegalMoveException
from .game import create_game
from .storage import ConnectionManager
from .types import Board, Character, EncounterActions, EncounterOutcome, Optional, Token


class Engine:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)
        self._board = ActiveBoard()
        self._characters = Party()

    def create_game(self, player_id: int, name: str, json_dir: Path) -> int:
        with ConnectionManager(player_id=player_id, game_id=None):
            game = create_game(name, json_dir)
            # create_game fixes the game_id in the session, so we can just call this:
            self._board.generate_hexes()
            return game.id

    def get_board(self, player_id: int, game_id: int) -> Board:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            return self._board.get_snapshot()

    def add_character(
        self,
        player_id: int,
        game_id: int,
        character_name: str,
        location: str,
        job_name: str,
    ) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            self._characters.create_character(
                name=character_name,
                player_id=player_id,
                job_name=job_name,
                board=self._board,
                location=location,
            )

    def get_character(
        self, player_id: int, game_id: int, character_name: str
    ) -> Character:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            return self._characters.get_character(character_name, self._board)

    def start_season(self, player_id: Optional[int], game_id: int) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            self._characters.start_season(self._board)

    def do_job(
        self, player_id: int, game_id: int, character_name: str, card_id: int
    ) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            self._characters.do_job(character_name, card_id, self._board)

    def do_travel(
        self, player_id: int, game_id: int, character_name: str, route: Sequence[str]
    ) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            self._characters.do_travel(character_name, route, self._board)

    def do_camp(self, player_id: int, game_id: int, character_name: str) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            self._characters.do_camp(character_name, self._board)

    def do_resolve_encounter(
        self,
        player_id: int,
        game_id: int,
        character_name: str,
        actions: EncounterActions,
    ) -> EncounterOutcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            return self._characters.resolve_encounter(
                character_name, actions, self._board
            )
