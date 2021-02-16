import functools
from traceback import print_exc
from typing import Any, Dict, Type, TypeVar

from picaro.common.serializer import deserialize, recursive_to_dict, serialize
from picaro.engine import Engine
from picaro.engine.exceptions import IllegalMoveException, BadStateException

from . import bottle
from .api_types import (
    CampRequest,
    CampResponse,
    Character,
    ErrorResponse,
    ErrorType,
    ResolveEncounterRequest,
    ResolveEncounterResponse,
    JobRequest,
    JobResponse,
    TravelRequest,
    TravelResponse,
)


def wrap_errors():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            type: ErrorType
            message = ""
            try:
                response = func(*args, **kwargs)
                return bottle.HTTPResponse(status=200, body=serialize(response))
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
            return bottle.HTTPResponse(status=418, body=serialize(response))

        return wrapper

    return decorator


T = TypeVar("T")


class Server:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @wrap_errors()
    def get_board(self, game_id: int) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        return recursive_to_dict(self._engine.get_board(player_id, game_id))

    @wrap_errors()
    def get_character(self, game_id: int, character_name: str) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        return recursive_to_dict(
            Character.from_engine_Character(
                self._engine.get_character(player_id, game_id, character_name)
            )
        )

    @wrap_errors()
    def job_action(self, game_id: int, character_name: str) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        req = self._read_body(JobRequest)
        self._engine.do_job(player_id, game_id, character_name, req.card_id)
        return recursive_to_dict(JobResponse())

    @wrap_errors()
    def travel_action(self, game_id: int, character_name: str) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        req = self._read_body(TravelRequest)
        self._engine.do_travel(player_id, game_id, character_name, req.route)
        return recursive_to_dict(TravelResponse())

    @wrap_errors()
    def camp_action(self, game_id: int, character_name: str) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        req = self._read_body(CampRequest)
        self._engine.do_camp(player_id, game_id, character_name)
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return recursive_to_dict(CampResponse())

    @wrap_errors()
    def resolve_encounter_action(
        self, game_id: int, character_name: str
    ) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        req = self._read_body(ResolveEncounterRequest)
        outcome = self._engine.do_resolve_encounter(
            player_id, game_id, character_name, req.actions
        )
        return recursive_to_dict(ResolveEncounterResponse(outcome=outcome))

    def run(self) -> None:
        bottle.route(path="/game/<game_id>/board", callback=self.get_board)
        bottle.route(
            path="/game/<game_id>/character/<character_name>",
            callback=self.get_character,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/job",
            method="POST",
            callback=self.job_action,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/travel",
            method="POST",
            callback=self.travel_action,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/camp",
            method="POST",
            callback=self.camp_action,
        )
        bottle.route(
            path="/game/<game_id>/play/<character_name>/resolve_encounter",
            method="POST",
            callback=self.resolve_encounter_action,
        )
        bottle.run(host="localhost", port=8080, debug=True)

    def _extract_player_id(self) -> int:
        return 103

    def _read_body(self, cls: Type[T]) -> T:
        return deserialize(bottle.request.body.read(), cls)
