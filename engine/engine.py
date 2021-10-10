import dataclasses
import functools
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from picaro.rules.activity import ActivityRules
from picaro.rules.base import RulesManager
from picaro.rules.game import GameRules
from picaro.rules.search import SearchRules
from picaro.rules.snapshot import (
    Action,
    Board,
    Character,
    CreateGameData,
    EncounterCommands,
    Entity,
    Game,
    Hex,
    Job,
    Record,
    Token,
)
from picaro.store.base import ConnectionManager


def with_context() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            game_uuid = kwargs.get("game_uuid", None)
            player_uuid = kwargs.get("player_uuid", None)
            character_name = kwargs.get("character_name", None)
            with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
                with RulesManager(character_name):
                    return func(*args, **kwargs)

        return wrapper

    return decorator


class Engine:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)

    def xyzzy(self) -> None:
        from pathlib import Path

        from picaro.client.generate import generate_game_v2

        json_dir = Path(__file__).absolute().parent.parent / "hyboria"
        data = generate_game_v2("Hyboria", json_dir)

        player_uuid = "inkyinkyinky"
        game_uuid = self.create_game(player_uuid=player_uuid, data=data)
        self.add_character(
            game_uuid=game_uuid,
            player_uuid=player_uuid,
            character_name="Conan",
            location="random",
            job_name="Raider",
        )
        other_player_uuid = "snickersabcd"
        self.add_character(
            game_uuid=game_uuid,
            player_uuid=other_player_uuid,
            character_name="Taurus",
            location="random",
            job_name="Merchant",
        )

        @with_context()
        def plugh(*, player_uuid: int, game_uuid: str) -> None:
            from picaro.store.character import Character
            from picaro.store.common_types import (
                Overlay,
                OverlayType,
                Filter,
                FilterType,
            )
            from picaro.store.gadget import Gadget

            ch = Character.load_by_name("Conan")
            Gadget.create(
                uuid="123",
                name="Cloak of Elvenkind",
                entity=ch.uuid,
                triggers=[],
                overlays=[
                    Overlay(
                        uuid="123.456",
                        type=OverlayType.SKILL_RANK,
                        subtype="Stealth",
                        value=1,
                        is_private=True,
                        filters=(),
                    ),
                    Overlay(
                        uuid="123.457",
                        type=OverlayType.SKILL_RANK,
                        subtype="Stealth",
                        value=1,
                        is_private=True,
                        filters=(
                            Filter(
                                type=FilterType.SKILL_GTE, subtype="Stealth", value=2
                            ),
                        ),
                    ),
                ],
                actions=[],
            )

        plugh(game_uuid=game_uuid, player_uuid=player_uuid)

        # with Character.load(character_name) as ch:
        #     loc = ch.get_snapshot().location
        #     ch.apply_regardless(
        #         [
        #             Effect(type=EffectType.MODIFY_COINS, value=50),
        #             Effect(type=EffectType.MODIFY_RESOURCES, value=10),
        #             Effect(type=EffectType.MODIFY_XP, subtype="Stealth", value=20),
        #             Effect(type=EffectType.MODIFY_XP, subtype="Brutal Fighting", value=25),
        #         ],
        #         [],
        #     )

        # project_name = "Quest for Sandwiches"
        # Project.create(project_name, "Monument", loc)
        # with Project.load(project_name) as proj:
        #     from .types import TaskType

        #     proj.add_task(TaskType.CHALLENGE)

        # with Task.load(project_name + " Task 1") as task:
        #     task.start(character_name, [])

    @with_context()
    def create_game(self, data: CreateGameData, *, player_uuid: int) -> str:
        game = GameRules.create_game(data)
        return game.uuid

    @with_context()
    def search_games(self, name: Optional[str], *, player_uuid: int) -> List[Game]:
        return SearchRules.search_games(name)

    @with_context()
    def add_character(
        self,
        location: str,
        job_name: str,
        *,
        player_uuid: int,
        game_uuid: str,
        character_name: str,
    ) -> None:
        GameRules.add_character(character_name, player_uuid, job_name, location)

    @with_context()
    def get_board(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> Board:
        return SearchRules.search_boards()

    @with_context()
    def search_entities(
        self, details: bool, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> List[Entity]:
        return SearchRules.search_entities(details)

    @with_context()
    def get_character(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> Character:
        return SearchRules.search_characters(character_name)[0]

    @with_context()
    def search_resources(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> List[str]:
        return SearchRules.search_resources()

    @with_context()
    def search_skills(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> List[str]:
        return SearchRules.search_skills()

    @with_context()
    def search_jobs(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> List[Job]:
        return SearchRules.search_jobs()

    @with_context()
    def search_actions(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> List[Action]:
        return SearchRules.search_actions(character_name)

    @with_context()
    def do_job(
        self, card_uuid: str, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> Sequence[Record]:
        return ActivityRules.do_job(character_name, card_uuid)

    @with_context()
    def perform_action(
        self,
        action_uuid: str,
        *,
        player_uuid: int,
        game_uuid: str,
        character_name: str,
    ) -> Sequence[Record]:
        return ActivityRules.perform_action(character_name, action_uuid)

    @with_context()
    def camp(
        self, player_uuid: int, game_uuid: str, character_name: str
    ) -> Sequence[Record]:
        return ActivityRules.camp(character_name)

    @with_context()
    def travel(
        self, hex: str, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> Sequence[Record]:
        return ActivityRules.travel(character_name, hex)

    @with_context()
    def end_turn(
        self, *, player_uuid: int, game_uuid: str, character_name: str
    ) -> Sequence[Record]:
        return ActivityRules.end_turn(character_name)

    @with_context()
    def resolve_encounter(
        self,
        actions: EncounterCommands,
        *,
        player_uuid: int,
        game_uuid: str,
        character_name: str,
    ) -> Sequence[Record]:
        return ActivityRules.resolve_encounter(character_name, actions)
