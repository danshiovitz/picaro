import functools
from traceback import print_exc
from typing import Any, Callable, Dict, Type, TypeVar

from picaro.common.serializer import deserialize, recursive_to_dict, serialize
from picaro.engine import Engine
from picaro.engine.exceptions import IllegalMoveException, BadStateException

from . import bottle
from .api_types import (
    Board,
    CampRequest,
    CampResponse,
    Character,
    EndTurnRequest,
    EndTurnResponse,
    ErrorResponse,
    ErrorType,
    ResolveEncounterRequest,
    ResolveEncounterResponse,
    JobRequest,
    JobResponse,
    ReturnProjectStageRequest,
    ReturnProjectStageResponse,
    SearchProjectsResponse,
    StartProjectStageRequest,
    StartProjectStageResponse,
    TokenActionRequest,
    TokenActionResponse,
    TravelRequest,
    TravelResponse,
)


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
    def get_board(self, game_id: int, character_name: str) -> Board:
        player_id = self._extract_player_id()
        return self._engine.get_board(
            player_id=player_id, game_id=game_id, character_name=character_name
        )

    @wrap_errors()
    def get_character(self, game_id: int, character_name: str) -> Character:
        player_id = self._extract_player_id()
        return self._engine.get_character(
            player_id=player_id, game_id=game_id, character_name=character_name
        )

    @wrap_errors()
    def get_projects(self, game_id: int, character_name: str) -> SearchProjectsResponse:
        player_id = self._extract_player_id()
        include_all = bottle.request.query.all or False
        return SearchProjectsResponse(
            projects=self._engine.get_projects(
                include_all=include_all,
                player_id=player_id,
                game_id=game_id,
                character_name=character_name,
            )
        )

    @wrap_errors()
    def start_project_stage(
        self, game_id: int, character_name: str
    ) -> StartProjectStageResponse:
        player_id = self._extract_player_id()
        req = self._read_body(StartProjectStageRequest)
        outcome = self._engine.start_project_stage(
            project_stage_name=req.project_stage_name,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return StartProjectStageResponse(outcome=outcome)

    @wrap_errors()
    def return_project_stage(
        self, game_id: int, character_name: str
    ) -> ReturnProjectStageResponse:
        player_id = self._extract_player_id()
        req = self._read_body(ReturnProjectStageRequest)
        outcome = self._engine.return_project_stage(
            project_stage_name=req.project_stage_name,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return ReturnProjectStageResponse(outcome=outcome)

    @wrap_errors()
    def do_job(self, game_id: int, character_name: str) -> JobResponse:
        player_id = self._extract_player_id()
        req = self._read_body(JobRequest)
        outcome = self._engine.do_job(
            req.card_id,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return JobResponse(outcome=outcome)

    @wrap_errors()
    def token_action(self, game_id: int, character_name: str) -> TokenActionResponse:
        player_id = self._extract_player_id()
        req = self._read_body(TokenActionRequest)
        outcome = self._engine.token_action(
            req.token,
            req.action,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return TokenActionResponse(outcome=outcome)

    @wrap_errors()
    def travel(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(TravelRequest)
        outcome = self._engine.travel(
            req.step,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return TravelResponse(outcome=outcome)

    @wrap_errors()
    def camp(self, game_id: int, character_name: str) -> CampResponse:
        player_id = self._extract_player_id()
        req = self._read_body(CampRequest)
        outcome = self._engine.camp(
            player_id=player_id, game_id=game_id, character_name=character_name
        )
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return CampResponse(outcome=outcome)

    @wrap_errors()
    def resolve_encounter(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(ResolveEncounterRequest)
        outcome = self._engine.resolve_encounter(
            req.actions,
            player_id=player_id,
            game_id=game_id,
            character_name=character_name,
        )
        return ResolveEncounterResponse(outcome=outcome)

    @wrap_errors()
    def end_turn(self, game_id: int, character_name: str) -> EndTurnResponse:
        player_id = self._extract_player_id()
        req = self._read_body(EndTurnRequest)
        outcome = self._engine.end_turn(
            player_id=player_id, game_id=game_id, character_name=character_name
        )
        return EndTurnResponse(outcome=outcome)

    def run(self) -> None:
        bottle.route(
            path="/game/<game_id>/board/<character_name>", callback=self.get_board
        )
        bottle.route(
            path="/game/<game_id>/character/<character_name>",
            callback=self.get_character,
        )
        bottle.route(
            path="/game/<game_id>/projects/<character_name>",
            callback=self.get_projects,
        )
        bottle.route(
            path="/game/<game_id>/projects/<character_name>/start",
            method="POST",
            callback=self.start_project_stage,
        )
        bottle.route(
            path="/game/<game_id>/projects/<character_name>/return",
            method="POST",
            callback=self.return_project_stage,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/job",
            method="POST",
            callback=self.do_job,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/token_action",
            method="POST",
            callback=self.token_action,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/travel",
            method="POST",
            callback=self.travel,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/camp",
            method="POST",
            callback=self.camp,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/resolve_encounter",
            method="POST",
            callback=self.resolve_encounter,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/end_turn",
            method="POST",
            callback=self.end_turn,
        )
        bottle.run(host="localhost", port=8080, debug=True)  # type: ignore

    def _extract_player_id(self) -> int:
        return 103

    def _read_body(self, cls: Type[T]) -> T:
        return deserialize(bottle.request.body.read(), cls)
