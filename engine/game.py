#!/usr/bin/python3
from pathlib import Path
from typing import Any, List

from .exceptions import IllegalMoveException
from .snapshot import CreateGameData
from .storage import ConnectionManager, ObjectStorageBase
from .types import Game, Job, ProjectType, TemplateDeck


def create_game(
    name: str,
    skills: List[str],
    resources: List[str],
    project_types: List[ProjectType],
    zodiacs: List[str],
) -> Game:
    game = Game(
        id=0,
        name=name,
        skills=skills,
        resources=resources,
        project_types=project_types,
        zodiacs=zodiacs,
    )
    game_id = GameStorage.create(game)
    return GameStorage.load_by_id(game_id)


def load_game() -> Game:
    return GameStorage.load_current()


class GameStorage(ObjectStorageBase[Game]):
    TABLE_NAME = "game"
    PRIMARY_KEYS = {"id"}
    UNIQUE_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Game]:
        return cls._select_helper([], {}, game_filter=False)

    @classmethod
    def load_current(cls) -> Game:
        games = cls._select_helper([], {})
        if len(games) != 1:
            raise IllegalMoveException("No current game")
        return games[0]

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
