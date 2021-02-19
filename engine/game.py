#!/usr/bin/python3
from pathlib import Path
from typing import Any, List

from .exceptions import IllegalMoveException
from .storage import ConnectionManager, ObjectStorageBase
from .types import Game


def create_game(name: str, json_dir: Path) -> Game:
    game_id = GameStorage.create(Game(id=0, name=name))
    ConnectionManager.fix_game_id(game_id)
    for store in ConnectionManager.ALL_STORES:
        store.insert_initial_data(json_dir)
    return GameStorage.load_by_id(game_id)


class GameStorage(ObjectStorageBase[Game]):
    TABLE_NAME = "game"
    TYPE = Game
    PRIMARY_KEY = "id"

    @classmethod
    def load(cls) -> List[Game]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_id(cls, id: int) -> Game:
        games = cls._select_helper(["id = :id"], {"id": id})
        if not games:
            raise IllegalMoveException(f"No such game: {id}")
        return games[0]

    @classmethod
    def create(cls, game: Game) -> int:
        return cls._insert_helper([game])

    @classmethod
    def update(cls, game: Game) -> None:
        cls._update_helper(game)
