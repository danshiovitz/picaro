import functools
from traceback import print_exc
from typing import Any, Callable, Dict, Type, TypeVar

from picaro.common.exceptions import IllegalMoveException, BadStateException
from picaro.common.serializer import deserialize, serialize
from picaro.common.storage import ConnectionManager
from picaro.rules.activity import ActivityRules
from picaro.rules.base import RulesManager
from picaro.rules.game import GameRules
from picaro.rules.search import SearchRules

from . import bottle
from .api_types import *


def wrap_errors() -> Callable[[Callable[..., Any]], Callable[..., bottle.HTTPResponse]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., bottle.HTTPResponse]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> bottle.HTTPResponse:
            type: ErrorType
            message = ""
            try:
                response = func(*args, **kwargs)
                return bottle.HTTPResponse(status=200, body=serialize(response))  # type: ignore
            except IllegalMoveException as ime:
                type = ErrorType.ILLEGAL_MOVE
                message = str(ime)
            except BadStateException as bse:
                type = ErrorType.BAD_STATE
                message = str(bse)
            except Exception as e:
                type = ErrorType.UNKNOWN
                message = f"Unexpected: {e.__class__.__name__} {e}"
                print_exc()
            response = ErrorResponse(type=type, message=message)
            return bottle.HTTPResponse(status=418, body=serialize(response))  # type: ignore

        return wrapper

    return decorator


T = TypeVar("T")


class Server:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)
        self.hacky_setup()
        # self.flat_setup()

    def hacky_setup(self) -> None:
        # buncha hacky initial setup:
        from pathlib import Path

        from picaro.client.generate import generate_game_v2

        player_uuid = "inkyinkyinky"
        other_player_uuid = "snickersabcd"
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            json_dir = Path(__file__).absolute().parent.parent / "hyboria"
            data = generate_game_v2("Hyboria", json_dir)
            game = GameRules.create_game(data)

        with ConnectionManager(game_uuid=game.uuid, player_uuid=player_uuid):
            with RulesManager("Conan"):
                ch = GameRules.add_character("Conan", player_uuid, "Raider", "random")
                ch = GameRules.add_character(
                    "Taurus", other_player_uuid, "Merchant", "random"
                )

                from picaro.rules.types.common import (
                    Overlay,
                    OverlayType,
                    Filter,
                    FilterType,
                )
                from picaro.rules.types.store import Character, Gadget

                ch = Character.load_by_name("Conan")
                Gadget.create(
                    uuid="123",
                    name="Cloak of Elvenkind",
                    desc=None,
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
                                    type=FilterType.SKILL_GTE,
                                    subtype="Stealth",
                                    value=2,
                                ),
                            ),
                        ),
                        Overlay(
                            uuid="123.458",
                            type=OverlayType.RELIABLE_SKILL,
                            subtype="Stealth",
                            value=3,
                            is_private=True,
                            filters=(),
                        ),
                    ],
                    actions=[],
                )
                with Character.load_by_name_for_write("Conan") as ch:
                    GameRules.apply_regardless(
                        ch,
                        [
                            Effect(type=EffectType.MODIFY_COINS, value=50),
                            Effect(type=EffectType.MODIFY_RESOURCES, value=10),
                            Effect(
                                type=EffectType.MODIFY_XP, subtype="Stealth", value=20
                            ),
                            Effect(
                                type=EffectType.MODIFY_XP,
                                subtype="Brutal Fighting",
                                value=25,
                            ),
                        ],
                        [],
                    )

    def flat_setup(self) -> None:
        # buncha hacky initial setup:
        from picaro.rules.test.gen_flat import generate_flatworld

        player_uuid = "inkyinkyinky"
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            data = generate_flatworld()
            game = GameRules.create_game(data)

        with ConnectionManager(game_uuid=game.uuid, player_uuid=player_uuid):
            with RulesManager("AFGNCAAP"):
                ch = GameRules.add_character(
                    "AFGNCAAP", player_uuid, "Red Job 1", "random"
                )

                from picaro.rules.types.common import (
                    Overlay,
                    OverlayType,
                    Filter,
                    FilterType,
                )
                from picaro.rules.types.store import Character, Gadget

                with Character.load_by_name_for_write("AFGNCAAP") as ch:
                    GameRules.apply_regardless(
                        ch,
                        [
                            Effect(type=EffectType.MODIFY_COINS, value=50),
                            Effect(type=EffectType.MODIFY_RESOURCES, value=10),
                            Effect(
                                type=EffectType.MODIFY_XP, subtype="Skill 3", value=20
                            ),
                            Effect(
                                type=EffectType.MODIFY_XP,
                                subtype="Skill 5",
                                value=25,
                            ),
                        ],
                        [],
                    )

    @wrap_errors()
    def search_entities(
        self, game_uuid: str, character_name: str
    ) -> SearchEntitiesResponse:
        player_uuid = self._extract_player_uuid()
        details = self._parse_bool(bottle.request.query.details)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchEntitiesResponse(
                    entities=SearchRules.search_entities(details=details)
                )

    @wrap_errors()
    def search_hexes(self, game_uuid: str, character_name: str) -> SearchHexesResponse:
        player_uuid = self._extract_player_uuid()
        details = self._parse_bool(bottle.request.query.details)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchHexesResponse(hexes=SearchRules.search_hexes())

    @wrap_errors()
    def get_character(self, game_uuid: str, character_name: str) -> Character:
        player_uuid = self._extract_player_uuid()
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchRules.search_characters(character_name)[0]

    @wrap_errors()
    def search_actions(
        self, game_uuid: str, character_name: str
    ) -> SearchActionsResponse:
        player_uuid = self._extract_player_uuid()
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchActionsResponse(
                    actions=SearchRules.search_actions(character_name),
                )

    @wrap_errors()
    def search_resources(
        self, game_uuid: str, character_name: str
    ) -> SearchResourcesResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchResourcesResponse(
                    resources=SearchRules.search_resources(),
                )

    @wrap_errors()
    def search_skills(
        self, game_uuid: str, character_name: str
    ) -> SearchSkillsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchSkillsResponse(
                    skills=SearchRules.search_skills(),
                )

    @wrap_errors()
    def search_jobs(self, game_uuid: str, character_name: str) -> SearchJobsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchJobsResponse(
                    jobs=SearchRules.search_jobs(),
                )

    @wrap_errors()
    def do_job(self, game_uuid: str, character_name: str) -> JobResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(JobRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.do_job(character_name, req.card_uuid)
        return JobResponse(records=records)

    @wrap_errors()
    def perform_action(self, game_uuid: str, character_name: str) -> ActionResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ActionRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.perform_action(character_name, req.action_uuid)
        return ActionResponse(records=records)

    @wrap_errors()
    def travel(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(TravelRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.travel(character_name, req.step)
        return TravelResponse(records=records)

    @wrap_errors()
    def camp(self, game_uuid: str, character_name: str) -> CampResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CampRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.camp(character_name)
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return CampResponse(records=records)

    @wrap_errors()
    def resolve_encounter(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ResolveEncounterRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.resolve_encounter(character_name, req.commands)
        return ResolveEncounterResponse(records=records)

    @wrap_errors()
    def end_turn(self, game_uuid: str, character_name: str) -> EndTurnResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(EndTurnRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.end_turn(character_name)
        return EndTurnResponse(records=records)

    @wrap_errors()
    def create_game(self) -> CreateGameResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CreateGameRequest)
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            game = GameRules.create_game(req)
        return CreateGameResponse(game.uuid)

    @wrap_errors()
    def search_games(self) -> SearchGamesResponse:
        player_uuid = self._extract_player_uuid()
        name = bottle.request.query.name
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            return SearchGamesResponse(games=SearchRules.search_games(name=name))

    @wrap_errors()
    def add_character(
        self, game_uuid: str, character_name: str
    ) -> AddCharacterResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(AddCharacterRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                ch = GameRules.add_character(
                    character_name, player_uuid, req.job_name, req.location or "random"
                )
        return AddCharacterResponse(ch.uuid)

    def _parse_bool(self, val: str) -> bool:
        return val.lower() == "t"

    def run(self) -> None:
        bottle.route(
            path="/games",
            method="GET",
            callback=self.search_games,
        )
        bottle.route(
            path="/games/create",
            method="POST",
            callback=self.create_game,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/add",
            method="POST",
            callback=self.add_character,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/entities",
            callback=self.search_entities,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/hexes",
            callback=self.search_hexes,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/character",
            callback=self.get_character,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/actions",
            callback=self.search_actions,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/resources",
            callback=self.search_resources,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/skills",
            callback=self.search_skills,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/jobs",
            callback=self.search_jobs,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/job",
            method="POST",
            callback=self.do_job,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/action",
            method="POST",
            callback=self.perform_action,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/travel",
            method="POST",
            callback=self.travel,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/camp",
            method="POST",
            callback=self.camp,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/resolve_encounter",
            method="POST",
            callback=self.resolve_encounter,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/end_turn",
            method="POST",
            callback=self.end_turn,
        )
        bottle.run(host="localhost", port=8080, debug=True)  # type: ignore

    def _extract_player_uuid(self) -> int:
        return 103

    def _read_body(self, cls: Type[T]) -> T:
        return deserialize(bottle.request.body.read(), cls)
