from pathlib import Path
from typing import Optional, Sequence

from .board import load_board
from .character import load_party
from .exceptions import BadStateException, IllegalMoveException
from .game import create_game
from .snapshot import Board, Character
from .storage import ConnectionManager
from .types import EncounterActions, Outcome


class Engine:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)

    def create_game(self, player_id: int, name: str, json_dir: Path) -> int:
        with ConnectionManager(player_id=player_id, game_id=None):
            game = create_game(name, json_dir)
            # create_game fixes the game_id in the session, so we can just call this:
            board = load_board()
            board.generate_map()
            return game.id

    def get_board(self, player_id: int, game_id: int, character_name: str) -> Board:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            board = load_board()
            return board.get_snapshot(character_name)

    def add_character(
        self,
        player_id: int,
        game_id: int,
        character_name: str,
        location: str,
        job_name: str,
    ) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            party.create_character(
                name=character_name,
                player_id=player_id,
                job_name=job_name,
                location=location,
            )

    def get_character(
        self, player_id: int, game_id: int, character_name: str
    ) -> Character:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.get_character(character_name)

    def start_season(self, player_id: Optional[int], game_id: int) -> None:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            party.start_season()

    def do_job(
        self, player_id: int, game_id: int, character_name: str, card_id: int
    ) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.do_job(character_name, card_id)

    def token_action(
        self,
        player_id: int,
        game_id: int,
        character_name: str,
        token_name: str,
        action_name: str,
    ) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.token_action(character_name, token_name, action_name)

    def travel(
        self, player_id: int, game_id: int, character_name: str, step: str
    ) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.travel(character_name, step)

    def camp(self, player_id: int, game_id: int, character_name: str) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.camp(character_name)

    def resolve_encounter(
        self,
        player_id: int,
        game_id: int,
        character_name: str,
        actions: EncounterActions,
    ) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.resolve_encounter(character_name, actions)

    def end_turn(self, player_id: int, game_id: int, character_name: str) -> Outcome:
        with ConnectionManager(player_id=player_id, game_id=game_id):
            party = load_party()
            return party.end_turn(character_name)
