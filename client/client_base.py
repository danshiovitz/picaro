from argparse import ArgumentParser, Namespace
from dataclasses import replace as dataclasses_replace
from http.client import HTTPResponse
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Sequence,
    Type,
    TypeVar,
)
from urllib.parse import quote as url_quote
from urllib.request import HTTPErrorProcessor, Request, build_opener, urlopen

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.serializer import deserialize, serialize
from picaro.server.api_types import *


T = TypeVar("T")


class SingleCache(Generic[T]):
    def __init__(self, fetch_func: Callable[[], List[T]]) -> None:
        self._data: List[T] = []
        self._by_name: Dict[str, int] = []
        self._by_uuid: Dict[str, int] = []
        self._fetch_func = fetch_func

    def invalidate(self) -> None:
        self._data.clear()
        self._by_name.clear()
        self._by_uuid.clear()

    def get_all(self) -> List[T]:
        if not self._data:
            self.refill()
        return self._data

    def get_by_name(self, name: str) -> T:
        if not self._data:
            self.refill()
        if name in self._by_name:
            return self._data[self._by_name[name]]
        raise Exception(f"Name not found for {name}")

    def get_by_uuid(self, uuid: str) -> T:
        if not self._data:
            self.refill()
        if uuid in self._by_uuid:
            return self._data[self._by_uuid[uuid]]
        raise Exception(f"Id not found for {uuid}")

    def refill(self) -> None:
        self._data = self._fetch_func()
        self._by_name.clear()
        self._by_uuid.clear()
        if not self._data:
            return
        if hasattr(self._data[0], "name"):
            self._by_name = {v.name: idx for idx, v in enumerate(self._data)}
        if hasattr(self._data[0], "uuid"):
            self._by_uuid = {v.uuid: idx for idx, v in enumerate(self._data)}


class NonThrowingHTTPErrorProcessor(HTTPErrorProcessor):
    def http_response(self, request: Request, response: HTTPResponse) -> Any:
        return response


# Base client class, with code for talking to the server and caching data
class ClientBase:
    COMMANDS = []

    @classmethod
    def run(cls) -> None:
        args = cls.parse_args([cmd.add_command for cmd in cls.COMMANDS])
        client = cls(args)
        client.args.cmd(client)

    @classmethod
    def parse_args(cls, command_funcs: List[Callable[[Any], None]]) -> Namespace:
        parser = ArgumentParser()
        parser.add_argument("--host", type=str, default="http://localhost:8080")
        parser.add_argument("--game_name", type=str, default="Hyboria")
        parser.add_argument("--name", type=str, required=True)
        parser.set_defaults(cmd=lambda cli: parser.print_help())
        subparsers = parser.add_subparsers()

        for cmd_func in command_funcs:
            cmd_func(subparsers)
        return parser.parse_args()

    def __init__(self, args: Namespace) -> None:
        self.args = args

        self.base_url = self.args.host
        if self.base_url and self.base_url[-1] == "/":
            self.base_url = self.base_url[:-1]
        self.opener = build_opener(NonThrowingHTTPErrorProcessor)

        self.games = SingleCache[Game](lambda: self._get_games())
        self.entities = SingleCache[Entity](
            lambda: list(
                self._get(f"/entities?details=False", SearchEntitiesResponse).entities
            )
        )
        self.hexes = SingleCache[Hex](
            lambda: self._get(f"/hexes", SearchHexesResponse).hexes
        )
        self.resources = SingleCache[str](
            lambda: self._get(f"/resources", SearchResourcesResponse).resources
        )
        self.skills = SingleCache[str](
            lambda: self._get(f"/skills", SearchSkillsResponse).skills
        )
        self.jobs = SingleCache[Job](
            lambda: self._get(f"/jobs", SearchJobsResponse).jobs
        )
        self.characters = SingleCache[Character](lambda: self._refill_character())

    def _refill_character(self) -> List[Character]:
        ch = self._get(f"/character", Character)
        # need to fix up the corresponding entity's location
        if self.entities._data:
            idx = self.entities._by_uuid[ch.uuid]
            self.entities._data[idx] = dataclasses_replace(
                self.entities._data[idx], locations=(ch.location,)
            )
        return [ch]

    @property
    def character(self) -> Character:
        return list(self.characters.get_all())[0]

    def create_game(self, data: CreateGameRequest) -> str:
        # special handling since player name and game uuid aren't used
        url = self.base_url + "/games/create"
        request = Request(url, data=serialize(data).encode("utf-8"))
        resp = self._http_common(request, CreateGameResponse)
        self.games.invalidate()
        return resp.game_id

    def get_actions(self) -> Sequence[Action]:
        return self._get(f"/actions", SearchActionsResponse).actions

    def do_job(self, card_uuid: str) -> Sequence[Record]:
        resp = self._post(
            f"/play/job",
            JobRequest(card_uuid=card_uuid),
            JobResponse,
        )
        self.characters.invalidate()
        return resp.records

    def perform_action(self, action_uuid: str) -> Sequence[Record]:
        resp = self._post(
            f"/play/action",
            ActionRequest(action_uuid=action_uuid),
            ActionResponse,
        )
        self.characters.invalidate()
        return resp.records

    def camp(self) -> Sequence[Record]:
        resp = self._post(f"/play/camp", CampRequest(rest=True), CampResponse)
        self.characters.invalidate()
        return resp.records

    def travel(self, step: str) -> Sequence[Record]:
        resp = self._post(f"/play/travel", TravelRequest(step=step), TravelResponse)
        self.characters.invalidate()
        return resp.records

    def end_turn(self) -> Sequence[Record]:
        resp = self._post(f"/play/end_turn", EndTurnRequest(), EndTurnResponse)
        self.characters.invalidate()
        return resp.records

    def resolve_encounter(self, commands: EncounterCommands) -> Sequence[Record]:
        resp = self._post(
            f"/play/resolve_encounter",
            ResolveEncounterRequest(commands=commands),
            ResolveEncounterResponse,
        )
        self.characters.invalidate()
        return resp.records

    def _find_game_uuid(self) -> str:
        return self.games.get_by_name(self.args.game_name).uuid

    def _get_games(self) -> List[Game]:
        # special handling since we don't have game uuid yet
        url = self.base_url + f"/games?name={url_quote(self.args.game_name)}"
        request = Request(url)
        resp = self._http_common(request, SearchGamesResponse)
        return resp.games

    def _get(self, path: str, cls: Type[T]) -> T:
        game_uuid = self._find_game_uuid()
        url = self.base_url
        url += f"/game/{game_uuid}/{self.args.name}"
        url += path
        request = Request(url)
        return self._http_common(request, cls)

    def _post(self, path: str, input_val: Any, cls: Type[T]) -> T:
        game_uuid = self._find_game_uuid()
        url = self.base_url
        url += f"/game/{game_uuid}/{self.args.name}"
        url += path
        request = Request(url, data=serialize(input_val).encode("utf-8"))
        return self._http_common(request, cls)

    def _http_common(self, request: Request, cls: Type[T]) -> T:
        with self.opener.open(request) as response:
            data = response.read().decode("utf-8")
        if isinstance(response, HTTPResponse) and response.status == 200:
            return deserialize(data, cls)
        try:
            err = deserialize(data, ErrorResponse)
        except Exception:
            raise Exception(f"Failed to decode data: {data}")
        if err.type == ErrorType.ILLEGAL_MOVE:
            raise IllegalMoveException(err.message)
        else:
            raise BadStateException(err.message)
