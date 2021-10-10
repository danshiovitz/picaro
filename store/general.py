from dataclasses import dataclass
from typing import Any, List, Sequence

from picaro.common.exceptions import IllegalMoveException

from .base import StandardStorage, StandardWrapper
from .common_types import TemplateCard


@dataclass
class GameStorage(StandardStorage["GameStorage"]):
    TABLE_NAME = "game"

    uuid: str
    name: str
    skills: List[str]
    resources: List[str]
    zodiacs: List[str]

    @classmethod
    def load_by_name(cls, name: str) -> "GameStorage":
        games = cls._select_helper(["name = :name"], {"name": name})
        if not games:
            raise IllegalMoveException(f"No such game: {name}")
        return games[0]

    @classmethod
    def load_current(cls) -> "GameStorage":
        games = cls._select_helper([], {})
        if len(games) != 1:
            raise IllegalMoveException("No current game")
        return games[0]


class Game(StandardWrapper[GameStorage]):
    @classmethod
    def load(cls) -> "Game":
        data = GameStorage.load_current()
        return Game(data)

    @classmethod
    def load_for_write(cls) -> "Game":
        data = GameStorage.load_current()
        return Game(data, can_write=True)

    @classmethod
    def load_by_name(cls, name: str) -> "Game":
        data = GameStorage.load_by_name(name)
        return Game(data)


@dataclass
class TemplateDeckStorage(StandardStorage["TemplateDeckStorage"]):
    TABLE_NAME = "template_deck"

    name: str
    cards: Sequence[TemplateCard]


class TemplateDeck(StandardWrapper[TemplateDeckStorage]):
    pass
