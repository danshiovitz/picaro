import functools
from traceback import print_exc
from typing import Any, Callable, Dict, Type, TypeVar

from picaro.common.exceptions import IllegalMoveException, BadStateException
from picaro.common.serializer import deserialize, recursive_to_dict, serialize
from picaro.engine import Engine

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
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @wrap_errors()
    def get_board(self, game_uuid: str, character_name: str) -> Board:
        player_uuid = self._extract_player_uuid()
        return self._engine.get_board(
            player_uuid=player_uuid, game_uuid=game_uuid, character_name=character_name
        )

    @wrap_errors()
    def search_entities(
        self, game_uuid: str, character_name: str
    ) -> SearchEntitiesResponse:
        player_uuid = self._extract_player_uuid()
        details = self._parse_bool(bottle.request.query.details)
        return SearchEntitiesResponse(
            entities=self._engine.search_entities(
                details=details,
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def get_character(self, game_uuid: str, character_name: str) -> Character:
        player_uuid = self._extract_player_uuid()
        return self._engine.get_character(
            player_uuid=player_uuid, game_uuid=game_uuid, character_name=character_name
        )

    @wrap_errors()
    def search_actions(
        self, game_uuid: str, character_name: str
    ) -> SearchActionsResponse:
        player_uuid = self._extract_player_uuid()
        return SearchActionsResponse(
            actions=self._engine.search_actions(
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def get_projects(
        self, game_uuid: str, character_name: str
    ) -> SearchProjectsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        return SearchProjectsResponse(
            projects=self._engine.get_projects(
                include_all=include_all,
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def search_resources(
        self, game_uuid: str, character_name: str
    ) -> SearchResourcesResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        return SearchResourcesResponse(
            resources=self._engine.search_resources(
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def search_skills(
        self, game_uuid: str, character_name: str
    ) -> SearchSkillsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        return SearchSkillsResponse(
            skills=self._engine.search_skills(
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def search_jobs(self, game_uuid: str, character_name: str) -> SearchJobsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        return SearchJobsResponse(
            jobs=self._engine.search_jobs(
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def start_task(self, game_uuid: str, character_name: str) -> StartTaskResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(StartTaskRequest)
        records = self._engine.start_task(
            task_name=req.task_name,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return StartTaskResponse(records=records)

    @wrap_errors()
    def return_task(self, game_uuid: str, character_name: str) -> ReturnTaskResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ReturnTaskRequest)
        records = self._engine.return_task(
            task_name=req.task_name,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return ReturnTaskResponse(records=records)

    @wrap_errors()
    def search_oracles(
        self, game_uuid: str, character_name: str
    ) -> SearchOraclesResponse:
        player_uuid = self._extract_player_uuid()
        free = self._parse_bool(bottle.request.query.free)
        return SearchOraclesResponse(
            oracles=self._engine.search_oracles(
                free=free,
                player_uuid=player_uuid,
                game_uuid=game_uuid,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def get_oracle_cost(
        self, game_uuid: str, character_name: str
    ) -> GetOracleCostResponse:
        player_uuid = self._extract_player_uuid()
        cost = self._engine.get_oracle_cost(
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return GetOracleCostResponse(cost=cost)

    @wrap_errors()
    def create_oracle(
        self, game_uuid: str, character_name: str
    ) -> CreateOracleResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CreateOracleRequest)
        id, records = self._engine.create_oracle(
            request=req.request,
            payment_selections=req.payment_selections,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return CreateOracleResponse(uuid=uuid, records=records)

    @wrap_errors()
    def answer_oracle(
        self, game_uuid: str, character_name: str
    ) -> AnswerOracleResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(AnswerOracleRequest)
        records = self._engine.answer_oracle(
            oracle_id=req.uuid,
            response=req.response,
            proposal=req.proposal,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return AnswerOracleResponse(records=records)

    @wrap_errors()
    def confirm_oracle(
        self, game_uuid: str, character_name: str
    ) -> ConfirmOracleResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ConfirmOracleRequest)
        records = self._engine.confirm_oracle(
            oracle_id=req.uuid,
            confirm=req.confirm,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return ConfirmOracleResponse(records=records)

    @wrap_errors()
    def do_job(self, game_uuid: str, character_name: str) -> JobResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(JobRequest)
        records = self._engine.do_job(
            req.card_uuid,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return JobResponse(records=records)

    @wrap_errors()
    def perform_action(self, game_uuid: str, character_name: str) -> ActionResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ActionRequest)
        records = self._engine.perform_action(
            req.action_uuid,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return ActionResponse(records=records)

    @wrap_errors()
    def travel(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(TravelRequest)
        records = self._engine.travel(
            req.step,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return TravelResponse(records=records)

    @wrap_errors()
    def camp(self, game_uuid: str, character_name: str) -> CampResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CampRequest)
        records = self._engine.camp(
            player_uuid=player_uuid, game_uuid=game_uuid, character_name=character_name
        )
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return CampResponse(records=records)

    @wrap_errors()
    def resolve_encounter(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ResolveEncounterRequest)
        records = self._engine.resolve_encounter(
            req.actions,
            player_uuid=player_uuid,
            game_uuid=game_uuid,
            character_name=character_name,
        )
        return ResolveEncounterResponse(records=records)

    @wrap_errors()
    def end_turn(self, game_uuid: str, character_name: str) -> EndTurnResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(EndTurnRequest)
        records = self._engine.end_turn(
            player_uuid=player_uuid, game_uuid=game_uuid, character_name=character_name
        )
        return EndTurnResponse(records=records)

    @wrap_errors()
    def create_game(self) -> CreateGameResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CreateGameRequest)
        game_uuid = self._engine.create_game(
            data=req,
            player_uuid=player_uuid,
        )
        return CreateGameResponse(game_uuid)

    @wrap_errors()
    def search_games(self) -> SearchGamesResponse:
        player_uuid = self._extract_player_uuid()
        name = bottle.request.query.name
        return SearchGamesResponse(
            games=self._engine.search_games(
                name=name,
                player_uuid=player_uuid,
            )
        )

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
            path="/game/<game_uuid>/<character_name>/board", callback=self.get_board
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/entities",
            callback=self.search_entities,
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
            path="/game/<game_uuid>/<character_name>/projects",
            callback=self.get_projects,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/projects/start",
            method="POST",
            callback=self.start_task,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/projects/return",
            method="POST",
            callback=self.return_task,
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
            path="/game/<game_uuid>/<character_name>/oracles",
            method="GET",
            callback=self.search_oracles,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/oracles/cost",
            method="GET",
            callback=self.get_oracle_cost,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/oracles/create",
            method="POST",
            callback=self.create_oracle,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/oracles/answer",
            method="POST",
            callback=self.answer_oracle,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/oracles/confirm",
            method="POST",
            callback=self.confirm_oracle,
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
