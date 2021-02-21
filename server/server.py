import functools
from traceback import print_exc
from typing import Any, Callable, Dict, Type, TypeVar

from picaro.common.serializer import deserialize, recursive_to_dict, serialize
from picaro.engine import Engine
from picaro.engine.exceptions import IllegalMoveException, BadStateException

from . import bottle
from .api_types import (
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
    def get_board(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        return self._engine.get_board(player_id, game_id, character_name)

    @wrap_errors()
    def get_character(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        return self._engine.get_character(player_id, game_id, character_name)

    @wrap_errors()
    def do_job(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(JobRequest)
        self._engine.do_job(player_id, game_id, character_name, req.card_id)
        return JobResponse()

    @wrap_errors()
    def token_action(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(TokenActionRequest)
        self._engine.token_action(player_id, game_id, character_name, req.token, req.action)
        return TokenActionResponse()

    @wrap_errors()
    def travel(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(TravelRequest)
        self._engine.travel(player_id, game_id, character_name, req.step)
        return TravelResponse()

    @wrap_errors()
    def camp(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(CampRequest)
        self._engine.camp(player_id, game_id, character_name)
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return CampResponse()

    @wrap_errors()
    def resolve_encounter(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(ResolveEncounterRequest)
        outcome = self._engine.resolve_encounter(
            player_id, game_id, character_name, req.actions
        )
        return ResolveEncounterResponse(outcome=outcome)

    @wrap_errors()
    def end_turn(self, game_id: int, character_name: str) -> Any:
        player_id = self._extract_player_id()
        req = self._read_body(EndTurnRequest)
        self._engine.end_turn(player_id, game_id, character_name)
        return EndTurnResponse()

    def run(self) -> None:
        bottle.route(path="/game/<game_id>/board/<character_name>", callback=self.get_board)
        bottle.route(
            path="/game/<game_id>/character/<character_name>",
            callback=self.get_character,
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
