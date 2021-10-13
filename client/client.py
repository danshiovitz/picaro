import re
import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from http.client import HTTPResponse
from pathlib import Path
from string import ascii_lowercase
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
)
from urllib.parse import quote as url_quote
from urllib.request import HTTPErrorProcessor, Request, build_opener, urlopen

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.hexmap.display import (
    CubeCoordinate,
    DisplayInfo,
    OffsetCoordinate,
    render_simple,
    render_large,
)
from picaro.common.serializer import deserialize, serialize
from picaro.server.api_types import *

from .cache import LookupCache
from .colors import colors
from .generate import generate_game_v2
from .read import ComplexReader, read_selections, read_text
from .render import render_gadget, render_outcome, render_record

S = TypeVar("S")
T = TypeVar("T")


class NonThrowingHTTPErrorProcessor(HTTPErrorProcessor):
    def http_response(self, request: Request, response: HTTPResponse) -> Any:
        return response


class Client(LookupCache):
    @classmethod
    def run(cls) -> None:
        args = cls.parse_args()
        client = Client(args)
        client.args.cmd(client)

    @classmethod
    def parse_args(cls) -> Namespace:
        parser = ArgumentParser()
        parser.add_argument("--host", type=str, default="http://localhost:8080")
        parser.add_argument("--game_name", type=str, default="Hyboria")
        parser.add_argument("--name", type=str, required=True)
        parser.set_defaults(cmd=lambda cli: parser.print_help())
        subparsers = parser.add_subparsers()

        get_board_parser = subparsers.add_parser("board")
        get_board_parser.set_defaults(cmd=lambda cli: cli.get_board())
        get_board_parser.add_argument("--country", "--countries", action="store_true")
        get_board_parser.add_argument("--large", action="store_true")
        get_board_parser.add_argument("--center", type=str, default=None)

        get_character_parser = subparsers.add_parser("character")
        get_character_parser.set_defaults(cmd=lambda cli: cli.get_character())
        get_character_parser.add_argument("--all", action="store_true")

        play_parser = subparsers.add_parser("play")
        play_parser.set_defaults(cmd=lambda cli: cli.play())
        play_parser.add_argument("--season", action="store_true")

        generate_parser = subparsers.add_parser("generate")
        generate_parser.set_defaults(cmd=lambda cli: cli.generate_game())
        generate_parser.add_argument("--json_dir", type=str, required=True)

        return parser.parse_args()

    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.base_url = self.args.host
        if self.base_url and self.base_url[-1] == "/":
            self.base_url = self.base_url[:-1]
        self.terrains = {
            "Forest": (colors.fg.green, '"'),
            "Jungle": (colors.bold + colors.fg.green, "%"),
            "Hills": (colors.fg.orange, "n"),
            "Mountains": (colors.fg.darkgrey, "^"),
            "Plains": (colors.fg.lightgrey, "."),
            "Desert": (colors.fg.yellow, ":"),
            "Water": (colors.fg.blue, "~"),
            "City": (colors.fg.red, "#"),
            "Swamp": (colors.fg.magenta, "&"),
            "Coastal": (colors.fg.cyan, ";"),
            "Arctic": (colors.bold, "/"),
        }
        self.game_uuid_map: Dict[str, str] = {}
        self.cached_entities: Dict[str, Entity] = {}
        self.cached_hexes: List[Hex] = []
        self.cached_resources: List[str] = []
        self.cached_skills: List[str] = []
        self.cached_jobs: List[Job] = []

        self.opener = build_opener(NonThrowingHTTPErrorProcessor)

    def get_board(self) -> None:
        ch = self._get(f"/character", Character)
        board = self._get(f"/board", Board)
        entities = self.lookup_entities()

        coords = {hx.coordinate: hx for hx in board.hexes}
        tokens: Dict[str, List[Entity]] = defaultdict(list)
        for entity in entities:
            for location in entity.locations:
                tokens[location].append(entity)

        if self.args.large:

            def display(coord: OffsetCoordinate) -> DisplayInfo:
                hx = coords[coord]

                color, symbol = self.terrains[hx.terrain]
                body1 = hx.name + " "
                body2 = (hx.country + "     ")[0:5]
                body2 = body2[0:5]

                if hx.name in tokens:
                    body2 = (
                        colors.bold
                        + (tokens[hx.name][0].name + "     ")[0:5]
                        + colors.reset
                    )
                return DisplayInfo(
                    fill=color + symbol + colors.reset,
                    body1=body1,
                    body2=body2,
                )

            char_token = [t for t in board.tokens if t.name == self.args.name][0]
            center_name = self.args.center or char_token.location
            center_hx = [hx for hx in board.hexes if hx.name == center_name][0]
            for line in render_large(
                set(coords), display, center=center_hx.coordinate, radius=2
            ):
                print(line)

        else:
            for line in self._make_small_map(ch, board, show_country=self.args.country):
                print(line)

        if entities:
            print()
            for entity in entities:
                if entity.type == EntityType.CHARACTER:
                    print(entity)

        if self.args.country:
            ccount: Dict[str, int] = defaultdict(int)
            for hx in board.hexes:
                ccount[hx.country] += 1
            print(sorted(ccount.items()))

    def _make_small_map(
        self,
        ch: Character,
        board: Board,
        center: Optional[OffsetCoordinate] = None,
        radius: int = 2,
        show_country: bool = False,
        show_encounters: bool = False,
    ) -> List[str]:
        coords = {hx.coordinate: hx for hx in board.hexes}

        tokens: Dict[str, List[Entity]] = defaultdict(list)
        for entity in self.lookup_entities():
            for location in entity.locations:
                tokens[location].append(entity)

        encounters = (
            {card.location for card in ch.tableau} if show_encounters else set()
        )

        flagged_hexes = set()

        def display(coord: OffsetCoordinate) -> str:
            hx = coords[coord]

            rev = colors.reverse if hx.name in flagged_hexes else ""

            if hx.name in tokens:
                if tokens[hx.name][0].type == EntityType.CHARACTER:
                    return colors.bold + "@" + colors.reset
                elif tokens[hx.name][0].type == EntityType.LANDMARK:
                    if tokens[hx.name][0].subtype == "city":
                        return colors.fg.red + rev + "#" + colors.reset
                    elif tokens[hx.name][0].subtype == "mine":
                        color = colors.bg.magenta + colors.fg.black + rev
                        return color + "*" + colors.reset
                    else:
                        return colors.bold + colors.bg.orange + rev + "?" + colors.reset
                else:
                    return colors.bold + colors.fg.green + rev + "?" + colors.reset
            elif hx.name in encounters:
                return colors.bold + colors.bg.red + rev + "!" + colors.reset

            color, symbol = self.terrains[hx.terrain]
            if show_country:
                symbol = hx.country[0]
            return color + rev + symbol + colors.reset

        return render_simple(set(coords), 1, display, center=center, radius=radius)

    def get_character(self) -> None:
        ch = self._get(f"/character", Character)
        print(f"{ch.name} ({ch.player_uuid}) - a {ch.job} [{ch.location}]")
        print(f"Health: {ch.health}   Coins: {ch.coins}   Reputation: {ch.reputation}")
        resources = ", ".join(f"{v} {n}" for n, v in ch.resources.items())
        print(f"Resources: {resources}")
        print("Skills:")
        for sk, v in sorted(ch.skills.items()):
            if self.args.all or v > 0 or ch.skill_xp[sk] > 0:
                print(f"  {sk}: {v} ({ch.skill_xp[sk]} xp)")
        if not self.args.all:
            print("(Use --all to see all skills)")
        print()
        print("Emblems:")
        for emblem in ch.emblems:
            print(f"* {render_gadget(emblem)}")
        if not ch.emblems:
            print("* None")
        print()

    def play(self) -> None:
        while True:
            try:
                self._play_turn()
            except BadStateException as e:
                print(e)
                print()
                continue
            ch = self._get(f"/character", Character)
            if not self.args.season or ch.remaining_turns <= 0:
                return
            else:
                print("===========")
                print()

    def _play_turn(self) -> None:
        while True:
            ch = self._get(f"/character", Character)
            if ch.encounter:
                print()
                self._encounter(ch)
                print()
                continue
            if ch.acted_this_turn and ch.speed == 0:
                print("[Ending the turn.]")
                self._end_turn()
                continue

            if ch.remaining_turns > 0:
                input_callbacks = self._display_play(ch)
                self._input_play_action(input_callbacks)
                continue
            self._display_play(ch)
            return

    def _display_play(self, ch: Character) -> Dict[str, Callable[[str], bool]]:
        board = self._get(f"/board", Board)

        ch_hex = [hx for hx in board.hexes if hx.name == ch.location][0]
        minimap = self._make_small_map(
            ch,
            board,
            center=ch_hex.coordinate,
            radius=4,
            show_encounters=True,
        )

        display = []
        display.append(
            f"{ch.name} ({ch.player_uuid}) - a {ch.job} [{ch.location}, in {ch_hex.country}]"
        )
        display.append("")
        display.append(
            f"Health: {ch.health}/{ch.max_health}   Coins: {ch.coins}   Reputation: {ch.reputation}   Resources: {sum(ch.resources.values(), 0)}/{ch.max_resources}"
        )
        display.append(
            f" Turns: {ch.remaining_turns}       Luck: {ch.luck}        Speed: {ch.speed}/{ch.max_speed}"
        )
        display.append("")

        if ch.remaining_turns:
            lines, input_callbacks = self._compute_inputs(ch)
            display.extend(lines)
        else:
            input_callbacks: Dict[str, Callable[[str], bool]] = {}

        while len(display) < len(minimap):
            display.append("")

        pad: Callable[[str, int], str] = lambda val, width: val + " " * (
            width - len(val)
        )
        display = [
            pad(display[idx], 80) + (minimap[idx] if idx < len(minimap) else "")
            for idx in range(len(display))
        ]
        while display[-1].strip() == "":
            display.pop()

        print()
        for line in display:
            print(line)
        print()
        return input_callbacks

    def _compute_inputs(
        self, ch: Character
    ) -> Tuple[List[str], Dict[str, Callable[[str], bool]]]:
        lines: List[str] = []
        inputs: Dict[str, Callable[[str], bool]] = {}

        def dist(route) -> str:
            if route.type == RouteType.GLOBAL:
                return "global"
            elif route.type == RouteType.UNAVAILABLE:
                return "unavailable"
            ret = route.steps[-1] if route.steps else ch.location
            ret += f" - {len(route.steps)} away"
            if len(route.steps) > ch.speed:
                ret += " (too far)"
            return ret

        idx = 0
        for card in ch.tableau:
            bullet = ascii_lowercase[idx]
            lines.append(f"{bullet}. ({card.age}) {card.name} [{dist(card.route)}]:")
            if card.type == FullCardType.CHALLENGE:
                lines.append(f"       {self._check_str(card.data[0], ch)}")
            else:
                lines.append("")
            # can't save card in lambda because it gets reassigned
            inputs[bullet] = lambda _, uuid=card.uuid, route=card.route: self._job(
                uuid, route
            )
            idx += 1

        actions = list(self._get(f"/actions", SearchActionsResponse).actions)

        def route_sort(route):
            if route.type == RouteType.GLOBAL:
                return 1001
            elif route.type == RouteType.UNAVAILABLE:
                return 1002
            else:
                return len(route.steps)

        actions.sort(key=lambda v: (route_sort(v.route), v.name, v.uuid))

        for action in actions:
            bullet = ascii_lowercase[idx]
            lines.append(f"{bullet}. {action.name} [{dist(action.route)}]")
            # can't save action in lambda because it gets reassigned
            inputs[
                bullet
            ] = lambda _, uuid=action.uuid, route=action.route: self._perform_action(
                uuid, route
            )
            idx += 1
            if idx > 10:
                break

        lines.append("q. Quit")
        inputs["q"] = lambda _: self._quit()
        lines.append("t. Travel (uio.jkl)")
        inputs["t"] = lambda d: self._travel(d, ch.location, ch.speed)
        lines.append("x. Camp")
        inputs["x"] = lambda _: self._camp()
        lines.append("z. End Turn (if you don't want to do a job or camp)")
        inputs["z"] = lambda _: self._end_turn()

        return lines, inputs

    def _check_str(self, check: EncounterCheck, ch: Character) -> str:
        reward_name = render_outcome(check.reward)
        penalty_name = render_outcome(check.penalty)
        return (
            f"{check.skill} (1d8{ch.skills[check.skill]:+}) vs {check.target_number} "
            f"({reward_name} / {penalty_name})"
        )

    def _input_play_action(
        self, input_callbacks: Dict[str, Callable[[str], bool]]
    ) -> None:
        while True:
            ch = self._get(f"/character", Character)
            if ch.encounter:
                return
            print("Action? ", end="")
            line = input().lower().strip()
            if not line:
                continue
            if line[0] not in input_callbacks:
                print("Unknown action")
                print()
                continue

            try:
                records = input_callbacks[line[0]](line[1:].strip())
                break
            except IllegalMoveException as e:
                print(e)
                print()
                continue

        if records:
            ch = self._get(f"/character", Character)
            self._display_records(ch, records)
            print("[Hit return]")
            input()

    def _job(self, card_uuid: str, route: Route) -> Sequence[Record]:
        # if we didn't make it to the card's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if not self._travel_route(route):
            return []

        # otherwise start the main job
        resp = self._post(
            f"/play/job",
            JobRequest(card_uuid=card_uuid),
            JobResponse,
        )

        return resp.records

    def _perform_action(self, action_uuid: str, route: Route) -> Sequence[Record]:
        # if we didn't make it to the action's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if not self._travel_route(route):
            return []

        # otherwise start the action
        resp = self._post(
            f"/play/action",
            ActionRequest(action_uuid=action_uuid),
            ActionResponse,
        )
        return resp.records

    def _quit(self) -> None:
        print("Bye!")
        sys.exit(0)

    def _travel(self, dirs: str, start_loc: str, speed: int) -> Sequence[Record]:
        if not dirs:
            print(f"No directions supplied!")
            print()
            return []

        board = self._get(f"/board", Board)

        cubes = {
            CubeCoordinate.from_row_col(hx.coordinate.row, hx.coordinate.column): hx
            for hx in board.hexes
        }
        ch_hex = [hx for hx in board.hexes if hx.name == start_loc][0]
        cur = CubeCoordinate.from_row_col(
            ch_hex.coordinate.row, ch_hex.coordinate.column
        )

        dir_map = {
            "u": (-1, +1, 0),
            "i": (0, +1, -1),
            "o": (+1, 0, -1),
            ".": (0, 0, 0),
            "j": (-1, 0, +1),
            "k": (0, -1, +1),
            "l": (+1, -1, 0),
        }

        steps = []
        for d in dirs:
            if d not in dir_map:
                print(f"Bad direction {d}; should be in uio.jkl")
                print()
                return False
            xm, ym, zm = dir_map[d]
            cur = cur.step(xm, ym, zm)
            if cur not in cubes:
                print("That route leaves the board!")
                print()
                return False
            steps.append(cubes[cur].name)

        if len(steps) > speed:
            print(f"You have only {speed} speed remaining.")
            print()
            return

        self._travel_route(Route(type=RouteType.NORMAL, steps=steps))
        # records are always accounted for within travel_route
        return []

    def _camp(self) -> Sequence[Record]:
        resp = self._post(f"/play/camp", CampRequest(rest=True), CampResponse)
        return resp.records

    def _end_turn(self) -> Sequence[Record]:
        resp = self._post(f"/play/end_turn", EndTurnRequest(), EndTurnResponse)
        return resp.records

    def _encounter(self, ch: Character) -> bool:
        line = ch.encounter.name
        if ch.encounter.signs:
            signs = ", ".join(ch.encounter.signs)
            line += f" [signs: {signs}]"
        print(line)
        if ch.encounter.desc:
            print(ch.encounter.desc)

        return self._input_encounter_action(ch)

    def _input_encounter_action(self, ch: Character) -> bool:
        if ch.encounter.type == EncounterType.CHALLENGE:
            actions = self._input_encounter_checks(
                ch, ch.encounter.uuid, ch.encounter.data, ch.encounter.rolls
            )
        elif ch.encounter.type == EncounterType.CHOICE:
            actions = self._input_encounter_choices(
                ch, ch.encounter.uuid, ch.encounter.data, ch.encounter.rolls
            )
        else:
            raise Exception("Encounter with no checks or choices?")

        try:
            resp = self._post(
                f"/play/resolve_encounter",
                ResolveEncounterRequest(actions=actions),
                ResolveEncounterResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        print()
        print(f"The outcome of your encounter:")
        self._display_records(ch, resp.records)
        print("[Hit return]")
        input()
        return True

    def _input_encounter_checks(
        self,
        ch: Character,
        enc_uuid: str,
        checks: Sequence[EncounterCheck],
        rolls: Sequence[int],
    ) -> EncounterCommands:
        rolls = list(rolls[:])
        luck_spent = 0
        transfers = []
        adjusts = []
        flee = False

        while True:
            print()
            for idx, check in enumerate(checks):
                status = "SUCCESS" if rolls[idx] >= check.target_number else "FAILURE"
                print(
                    f"Check #{idx+1}: {self._check_str(check, ch)}: {rolls[idx]} - {status}"
                )
            print("You can go, transfer, adjust, or flee: ", end="")
            line = input().lower().strip()
            if not line:
                continue
            if line[0] == "f":
                if ch.luck - luck_spent <= 0:
                    print(f"Insufficient luck to flee!")
                    continue
                flee = True
                luck_spent += 1
                break
            elif line[0] == "t":
                m = re.match(r"^t\w*\s+([0-9]+)\s+([0-9]+)$", line)
                if not m:
                    print("Expected: transfer <from check num> <to check num>")
                    continue
                from_c = int(m.group(1)) - 1
                to_c = int(m.group(2)) - 1
                if not (0 <= from_c < len(rolls)):
                    print(f"Bad from check: {from_c + 1}")
                    continue
                if not (0 <= to_c < len(rolls)):
                    print(f"Bad to check: {to_c + 1}")
                    continue
                if rolls[from_c] < 2:
                    print(f"From roll has insufficient value ({rolls[from_c]})")
                    continue
                transfers.append((from_c, to_c))
                rolls[from_c] -= 2
                rolls[to_c] += 1
            elif line[0] == "a":
                m = re.match(r"^a\w*\s+([0-9]+)$", line)
                if not m:
                    print("Expected: adjust <check num>")
                    continue
                adj_c = int(m.group(1)) - 1
                if not (0 <= adj_c < len(rolls)):
                    print(f"Bad adjust check: {adj_c + 1}")
                    continue
                if ch.luck - luck_spent <= 0:
                    print(f"Luck has insufficient value")
                    continue
                adjusts.append(adj_c)
                rolls[adj_c] += 1
                luck_spent += 1
            elif line[0] == "g":
                break
            else:
                print("Unknown command!")
                continue

        return EncounterCommands(
            encounter_uuid=enc_uuid,
            flee=flee,
            transfers=transfers,
            adjusts=adjusts,
            luck_spent=luck_spent,
            rolls=rolls,
            choices={},
        )

    def _input_encounter_choices(
        self, ch: Character, enc_uuid: str, choices: Choices, rolls: Sequence[int]
    ) -> EncounterCommands:
        selections = read_selections(choices, rolls, self)
        return EncounterCommands(
            encounter_uuid=enc_uuid,
            flee=False,
            transfers=[],
            adjusts=[],
            luck_spent=0,
            rolls=rolls,
            choices={k: v for k, v in selections.items() if v > 0},
        )

    def _display_records(self, ch: Character, records: List[Record]) -> None:
        if not records:
            return

        for record in records:
            print(render_record(ch, record, self))

    def _travel_route(self, route: Route) -> bool:
        if route.type == RouteType.GLOBAL:
            return True
        elif route.type == RouteType.UNAVAILABLE:
            print(f"There's no obvious way to get there.")
            return False

        for step in route.steps:
            resp = self._post(f"/play/travel", TravelRequest(step=step), TravelResponse)

            ch = self._get(f"/character", Character)
            # if there are records, display but keep walking:
            if resp.records:
                self._display_records(ch, resp.records)
                print("[Hit return]")
                input()

            if ch.encounter:
                print(f"Your journey is interrupted in {ch.location}!")
                return False
            elif ch.speed <= 0 and ch.location != route.steps[-1]:
                print(f"You only make it to {ch.location} this turn.")
                return False
        return True

    def generate_game(self) -> None:
        game_name = self.args.game_name
        json_dir = Path(self.args.json_dir)
        data = generate_game_v2(game_name, json_dir)
        # special handling since player name and game uuid aren't used
        url = self.base_url + "/games/create"
        request = Request(url, data=serialize(data).encode("utf-8"))
        resp = self._http_common(request, CreateGameResponse)
        print(f"Generated game named {self.args.game_name} (id {resp.game_id})")

    def lookup_entity(self, entity_uuid: str) -> Entity:
        for entity in self.lookup_entities():
            if entity.uuid == entity_uuid:
                return entity
        raise Exception(f"Still can't find {entity_uuid} in {self.cached_entities}")

    def lookup_entities(self) -> List[Entity]:
        if not self.cached_entities:
            entities = self._get(
                f"/entities?details=False", SearchEntitiesResponse
            ).entities
            self.cached_entities = {e.uuid: e for e in entities}
        return list(self.cached_entities.values())

    def lookup_hexes(self) -> List[Hex]:
        if not self.cached_hexes:
            hexes = self._get(f"/hexes", SearchHexesResponse).hexes
            self.cached_hexes = hexes
        return self.cached_hexes

    def lookup_resources(self) -> List[str]:
        if not self.cached_resources:
            resources = self._get(f"/resources", SearchResourcesResponse).resources
            self.cached_resources = resources
        return self.cached_resources

    def lookup_skills(self) -> List[str]:
        if not self.cached_skills:
            skills = self._get(f"/skills", SearchSkillsResponse).skills
            self.cached_skills = skills
        return self.cached_skills

    def lookup_jobs(self) -> List[Job]:
        if not self.cached_jobs:
            jobs = self._get(f"/jobs", SearchJobsResponse).jobs
            self.cached_jobs = jobs
        return self.cached_jobs

    def _find_game_uuid(self) -> None:
        game_name = self.args.game_name
        if game_name not in self.game_uuid_map:
            # special handling since we don't have game uuid yet
            url = self.base_url + f"/games?name={url_quote(game_name)}"
            request = Request(url)
            resp = self._http_common(request, SearchGamesResponse)
            for game in resp.games:
                self.game_uuid_map[game.name] = game.uuid
        return self.game_uuid_map[game_name]

    def _get(self, path: str, cls: Type[T]) -> T:
        game_uuid = self._find_game_uuid()
        url = self.base_url
        url += f"/game/{game_uuid}/{self.args.name}"
        url += path
        request = Request(url)
        return self._http_common(request, cls)

    def _post(self, path: str, input_val: S, cls: Type[T]) -> T:
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


if __name__ == "__main__":
    args = Client.parse_args()
    args.cmd(args)
