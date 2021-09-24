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
from urllib.request import HTTPErrorProcessor, Request, build_opener, urlopen

from picaro.client.colors import colors
from picaro.common.hexmap.display import (
    CubeCoordinate,
    DisplayInfo,
    OffsetCoordinate,
    render_simple,
    render_large,
)
from picaro.common.serializer import deserialize, serialize
from picaro.server.api_types import *

from .common import BadStateException, IllegalMoveException
from .generate import generate_game_v2
from .read import ComplexReader, read_selections, read_text
from .render import render_effect, render_gadget, render_outcome, render_record

S = TypeVar("S")
T = TypeVar("T")


class NonThrowingHTTPErrorProcessor(HTTPErrorProcessor):
    def http_response(self, request: Request, response: HTTPResponse) -> Any:
        return response


class Client:
    @classmethod
    def run(cls) -> None:
        args = cls.parse_args()
        client = Client(args)
        client.args.cmd(client)

    @classmethod
    def parse_args(cls) -> Namespace:
        parser = ArgumentParser()
        parser.add_argument("--host", type=str, default="http://localhost:8080")
        parser.add_argument("--game_id", type=int, default=1)
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

        do_projects_parser = subparsers.add_parser("projects")
        do_projects_parser.set_defaults(cmd=lambda cli: cli.do_projects())
        do_projects_parser.add_argument("--all", action="store_true")
        do_projects_parser.add_argument("--start", action="store_true")
        do_projects_parser.add_argument("--do_return", "--return", action="store_true")

        do_oracle_parser = subparsers.add_parser("oracle")
        oracle_subparsers = do_oracle_parser.add_subparsers()
        create_oracle_parser = oracle_subparsers.add_parser("create")
        create_oracle_parser.set_defaults(cmd=lambda cli: cli.create_oracle())
        answer_oracle_parser = oracle_subparsers.add_parser("answer")
        answer_oracle_parser.set_defaults(cmd=lambda cli: cli.answer_oracle())
        confirm_oracle_parser = oracle_subparsers.add_parser("confirm")
        confirm_oracle_parser.set_defaults(cmd=lambda cli: cli.confirm_oracle())
        list_oracle_parser = oracle_subparsers.add_parser("list")
        list_oracle_parser.set_defaults(cmd=lambda cli: cli.list_oracles())

        play_parser = subparsers.add_parser("play")
        play_parser.set_defaults(cmd=lambda cli: cli.play())
        play_parser.add_argument("--season", action="store_true")

        generate_parser = subparsers.add_parser("generate")
        generate_parser.set_defaults(cmd=lambda cli: cli.generate_game())
        generate_parser.add_argument("--game_name", type=str, required=True)
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
        self.opener = build_opener(NonThrowingHTTPErrorProcessor)

    def get_board(self) -> None:
        ch = self._get(f"/character", Character)
        board = self._get(f"/board", Board)
        coords = {hx.coordinate: hx for hx in board.hexes}

        tokens: Dict[str, List[Token]] = defaultdict(list)
        for tok in board.tokens:
            tokens[tok.location].append(tok)

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

        if board.tokens:
            print()
            for tok in board.tokens:
                if tok.type == "Character" or len(tok.route) <= 5:
                    print(tok)

        if self.args.country:
            ccount: Dict[str, int] = defaultdict(int)
            for hx in board.hexes:
                ccount[hx.country] += 1
            print(sorted(ccount.items()))

    def _make_small_map(
        self,
        ch: Character,
        board: Board,
        show_country: bool = False,
        center: Optional[OffsetCoordinate] = None,
        radius: int = 2,
        encounters: Optional[Set[str]] = None,
    ) -> List[str]:
        coords = {hx.coordinate: hx for hx in board.hexes}

        tokens: Dict[str, List[Token]] = defaultdict(list)
        for tok in board.tokens:
            tokens[tok.location].append(tok)

        flagged_hexes = set()
        for task in ch.tasks:
            if task.type == TaskType.DISCOVERY:
                flagged_hexes |= set(task.extra.possible_hexes)

        def display(coord: OffsetCoordinate) -> str:
            hx = coords[coord]

            rev = colors.reverse if hx.name in flagged_hexes else ""

            if hx.name in tokens:
                if tokens[hx.name][0].type == EntityType.CHARACTER:
                    return colors.bold + "@" + colors.reset
                elif tokens[hx.name][0].type == EntityType.CITY:
                    return colors.fg.red + rev + "#" + colors.reset
                elif tokens[hx.name][0].type == EntityType.MINE:
                    return (
                        colors.bg.magenta + colors.fg.black + rev + "*" + colors.reset
                    )
                elif tokens[hx.name][0].type == EntityType.PROJECT:
                    return colors.bold + colors.bg.orange + rev + "P" + colors.reset
                elif tokens[hx.name][0].type == EntityType.TASK:
                    return colors.bold + colors.bg.orange + rev + "T" + colors.reset
                else:
                    return colors.bold + colors.fg.green + rev + "?" + colors.reset
            elif encounters is not None and hx.name in encounters:
                return colors.bold + colors.bg.red + rev + "!" + colors.reset

            color, symbol = self.terrains[hx.terrain]
            if show_country:
                symbol = hx.country[0]
            return color + rev + symbol + colors.reset

        return render_simple(set(coords), 1, display, center=center, radius=radius)

    def get_character(self) -> None:
        ch = self._get(f"/character", Character)
        print(f"{ch.name} ({ch.player_id}) - a {ch.job} [{ch.location}]")
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

    def do_projects(self) -> None:
        ch = self._get(f"/character", Character)

        is_all = "?all=true" if self.args.all or self.args.start else ""
        resp = self._get(f"/projects{is_all}", SearchProjectsResponse)
        projects = resp.projects
        print(f"All Current Projects:" if is_all else "Your Current Projects:")
        if not projects:
            print("* None")
            return

        choices = []
        for project in projects:
            print(
                f"* {project.name} ({project.type}, {project.status.name}) @ {project.target_hex}"
            )
            print(f"  {project.desc}")
            print(f"  Tasks:")
            tasks = project.tasks
            if self.args.start:
                tasks = [s for s in tasks if s.status == TaskStatus.UNASSIGNED]
            elif self.args.do_return:
                tasks = [
                    s
                    for s in tasks
                    if s.status == TaskStatus.IN_PROGRESS and ch.name in s.participants
                ]

            if not tasks:
                print("  * None")
                print()
                continue
            for task in tasks:
                if self.args.start or self.args.do_return:
                    ltr = ascii_lowercase[len(choices)]
                    choices.append(task.name)
                    print(
                        f"  {ltr}. {task.name} ({task.type.name}) - {task.xp}/{task.max_xp}"
                    )
                else:
                    print(
                        f"  * {task.name} ({task.type.name}, {task.status.name}) - {task.xp}/{task.max_xp} [{', '.join(task.participants)}]"
                    )
                if task.desc:
                    print(f"    {task.desc}")
                if task.type == TaskType.CHALLENGE:
                    print(f"    Skills: {', '.join(sorted(task.extra.skills))}")
                elif task.type == TaskType.RESOURCE:
                    print(
                        f"    Wanted: {', '.join(sorted(task.extra.wanted_resources))}; Given: {task.extra.given_resources}"
                    )
                elif task.type == TaskType.WAITING:
                    print(f"    Turns Waited: {task.extra.turns_waited}")
                elif task.type == TaskType.DISCOVERY:
                    print(
                        f"    Possible Hexes: {', '.join(sorted(task.extra.possible_hexes))}"
                    )
                else:
                    print(f"    Unknown Task Type: {task.extra}")

        if (self.args.start or self.args.do_return) and choices:
            verb = "start" if self.args.start else "return"
            while True:
                print(f"Task to {verb}? ", end="")
                line = input().lower().strip()
                if not line:
                    continue

                if line[0] == "q":
                    print(f"[Not {verb}ing any task]")
                    return

                c_idx = ascii_lowercase.index(line[0])
                if c_idx >= len(choices):
                    print("No such task!")
                    print()
                    continue

                try:
                    if self.args.start:
                        pargs = [
                            f"/projects/start",
                            StartTaskRequest(choices[c_idx]),
                            StartTaskResponse,
                        ]
                    else:
                        pargs = [
                            f"/projects/return",
                            ReturnTaskRequest(choices[c_idx]),
                            ReturnTaskResponse,
                        ]

                    resp = self._post(*pargs)
                    if resp.records:
                        self._display_records(ch, resp.records)
                        print("[Hit return]")
                        input()
                    return
                except IllegalMoveException as e:
                    print(e)
                    print()
                    continue

    def create_oracle(self) -> None:
        ch = self._get(f"/character", Character)
        resp = self._get(f"/oracles/cost", GetOracleCostResponse)
        print(f"How will you pay for the oracle?")
        selections = read_selections(resp.cost, [])
        request = read_text("Describe the request you make:", textbox=True)
        try:
            resp = self._post(
                f"/oracles/create",
                CreateOracleRequest(request=request, payment_selections=selections),
                CreateOracleResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
        else:
            print("Your request has been sent")

    def answer_oracle(self) -> None:
        ch = self._get(f"/character", Character)
        resp = self._get(f"/oracles?free=true", SearchOraclesResponse)
        oracles = resp.oracles

        print("Oracles awaiting answers:")
        if not oracles:
            print(" * None")
            return
        for idx, oracle in enumerate(oracles):
            self._display_oracle_item(oracle, bullet=f"{ascii_lowercase[idx]}.")
        print(" q. Quit")
        while True:
            print("Which? ", end="")
            line = input().strip().lower()
            if not line:
                continue
            if line[0] == "q":
                return
            oidx = ascii_lowercase.find(line[0])
            if oidx < 0 or oidx >= len(oracles):
                print("No such oracle?")
                continue
            oracle = oracles[oidx]
            break

        payment = ", ".join(render_effect(e) for e in oracle.payment)
        print(
            f"Petitioner: {oracle.petitioner}    Payment: {payment}    [{', '.join(oracle.signs)}]"
        )
        print(oracle.request)
        response = read_text("Give your response:", textbox=True)
        board = self._get(f"/board", Board)
        skills = self._get(f"/skills", SearchSkillsResponse).skills
        jobs = self._get(f"/jobs", SearchJobsResponse).jobs
        reader = ComplexReader(
            default_entity=(EntityType.CHARACTER, oracle.petitioner),
            board=board,
            skills=skills,
            jobs=jobs,
        )
        proposal = reader.read_effects("Propose mechanics for this oracle:", [])
        try:
            resp = self._post(
                f"/oracles/answer",
                AnswerOracleRequest(id=oracle.id, response=response, proposal=proposal),
                AnswerOracleResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
        else:
            print("Your response has been sent")

    def confirm_oracle(self) -> None:
        ch = self._get(f"/character", Character)
        resp = self._get(f"/oracles", SearchOraclesResponse)
        oracles = [o for o in resp.oracles if o.status == OracleStatus.ANSWERED]

        print("Oracles awaiting confirmation:")
        if not oracles:
            print(" * None")
            return
        for idx, oracle in enumerate(oracles):
            self._display_oracle_item(oracle, bullet=f"{ascii_lowercase[idx]}.")
        print(" q. Quit")
        while True:
            print("Which? ", end="")
            line = input().strip().lower()
            if not line:
                continue
            if line[0] == "q":
                return
            oidx = ascii_lowercase.find(line[0])
            if oidx < 0 or oidx >= len(oracles):
                print("No such oracle?")
                continue
            oracle = oracles[oidx]
            break

        print("The request:")
        print(oracle.request)
        print()
        print("The response:")
        print(oracle.response)
        for eff in oracle.proposal:
            print(f" * {render_effect(eff)}")

        confirm = None
        while True:
            print("You can confirm, reject, or quit: ", end="")
            line = input().strip().lower()
            if not line:
                continue
            if line[0] == "q":
                return
            elif line[0] == "c":
                confirm = True
                break
            elif line[0] == "r":
                confirm = False
                break
            else:
                print("???")
                continue

        try:
            resp = self._post(
                f"/oracles/confirm",
                ConfirmOracleRequest(id=oracle.id, confirm=confirm),
                ConfirmOracleResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
        else:
            print(f"You have {'confirm' if confirm else 'reject'}ed this oracle.")

    def list_oracles(self) -> None:
        ch = self._get(f"/character", Character)
        resp = self._get(f"/oracles", SearchOraclesResponse)
        oracles = resp.oracles

        print("Current Oracles:")
        if not oracles:
            print(" * None")
            return
        for oracle in oracles:
            self._display_oracle_item(oracle)

    def _display_oracle_item(self, oracle: Oracle, bullet: str = "*") -> None:
        if len(oracle.request) > 70:
            rt = oracle.request[0:70] + "..."
        else:
            rt = oracle.request
        rt = rt.replace("\n", " ")
        print(f" {bullet} {rt}")
        sp = " " * len(bullet)
        print(
            f" {sp} Petitioner: {oracle.petitioner}   Granter: {oracle.granter or '<none>'}   Status: {oracle.status.name.lower()}"
        )

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
                self._end_turn(ch)
                continue

            if ch.remaining_turns > 0:
                self._display_play(ch)
                self._input_play_action()
                continue
            self._display_play(ch)
            return

    def _display_play(self, ch: Character) -> None:
        board = self._get(f"/board", Board)
        encounters = {card.location for card in ch.tableau}

        ch_hex = [hx for hx in board.hexes if hx.name == ch.location][0]
        minimap = self._make_small_map(
            ch, board, center=ch_hex.coordinate, radius=4, encounters=encounters
        )

        display = []
        display.append(
            f"{ch.name} ({ch.player_id}) - a {ch.job} [{ch.location}, in {ch_hex.country}]"
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

            def dist(route) -> str:
                ret = f"- {len(route)} away"
                if len(route) > ch.speed:
                    ret += " (too far)"
                return ret

            for idx, card in enumerate(ch.tableau):
                display.append(
                    f"{ascii_lowercase[idx]}. ({card.age}) {card.name} [{card.location} {dist(card.route)}]:"
                )
                if card.type == FullCardType.CHALLENGE:
                    display.append(f"       {self._check_str(card.data[0], ch)}")
                else:
                    display.append("")

            actions = self._available_actions(board)
            for idx, token_action in enumerate(actions):
                token, action = token_action
                display.append(
                    f"{ascii_lowercase[idx + 9]}. {action.name} [{token.location} {dist(token.route)}]"
                )

            display.append("q. Quit")
            display.append("t. Travel (uio.jkl)")
            display.append("x. Camp")
            display.append("z. End Turn (if you don't want to do a job or camp)")
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

        for line in display:
            print(line)
        print()

    def _available_actions(self, board: Board) -> List[Tuple[Token, Action]]:
        actions = [(t, a) for t in board.tokens for a in t.actions if len(t.route) <= 5]
        actions.sort(key=lambda v: (v[0].location, len(v[0].route), v[1].name))
        return actions

    def _check_str(self, check: EncounterCheck, ch: Character) -> str:
        reward_name = render_outcome(check.reward)
        penalty_name = render_outcome(check.penalty)
        return (
            f"{check.skill} (1d8{ch.skills[check.skill]:+}) vs {check.target_number} "
            f"({reward_name} / {penalty_name})"
        )

    def _input_play_action(self) -> bool:
        while True:
            ch = self._get(f"/character", Character)
            if ch.encounter:
                return False
            print("Action? ", end="")
            line = input().lower().strip()
            if not line:
                continue
            if line[0] in "abcdefg":
                c_idx = "abcdefg".index(line[0])
                if c_idx < len(ch.tableau):
                    if self._job(ch.tableau[c_idx], ch):
                        return True
                else:
                    print("No such encounter card!")
                    print()
                    continue
            elif line[0] in "jklmnop":
                c_idx = "jklmnop".index(line[0])
                board = self._get(f"/board", Board)
                actions = self._available_actions(board)
                if c_idx < len(actions):
                    token, action = actions[c_idx]
                    if self._token_action(token, action, ch):
                        return True
                else:
                    print("No such action!")
                    print()
                    continue
            elif line[0] == "q":
                print("Bye!")
                sys.exit(0)
            elif line[0] == "t":
                ww = re.split(r"\s+", line, 2)
                dirs = "" if len(ww) == 1 else ww[1]
                self._travel(dirs, ch)
                return False
            elif line[0] == "x":
                if self._camp(ch):
                    return True
            elif line[0] == "z":
                if self._end_turn(ch):
                    return True
            else:
                print("Unknown action")
                print()
                continue

    def _job(self, card: TableauCard, ch: Character) -> bool:
        self._travel_route(card.route, ch)
        ch = self._get(f"/character", Character)
        # if we didn't make it to the card's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if ch.location != card.location or ch.encounter:
            # return true to force input play method to exit also
            return True

        # otherwise start the main job
        try:
            resp = self._post(
                f"/play/job",
                JobRequest(card_id=card.id),
                JobResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
            return True
        return True

    def _token_action(self, token: Token, action: Action, ch: Character) -> bool:
        self._travel_route(token.route, ch)
        ch = self._get(f"/character", Character)
        # if we didn't make it to the token's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if ch.location != token.location or ch.encounter:
            # return true to force input play method to exit also
            return True

        # otherwise start the action
        try:
            resp = self._post(
                f"/play/token_action",
                TokenActionRequest(token=token.name, action=action.name),
                TokenActionResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
            return True
        return True

    def _camp(self, ch: Character) -> bool:
        try:
            resp = self._post(f"/play/camp", CampRequest(rest=True), CampResponse)
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
            return True
        return True

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
                ch, ch.encounter.data, ch.encounter.rolls
            )
        elif ch.encounter.type == EncounterType.CHOICE:
            actions = self._input_encounter_choices(
                ch, ch.encounter.data, ch.encounter.rolls
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
        self, ch: Character, checks: Sequence[EncounterCheck], rolls: Sequence[int]
    ) -> EncounterActions:
        rolls = list(rolls[:])
        luck = ch.luck
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
                if luck <= 0:
                    print(f"Insufficient luck ({luck}) to flee!")
                    continue
                flee = True
                luck -= 1
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
                if luck <= 0:
                    print(f"Luck has insufficient value ({luck})")
                    continue
                adjusts.append(adj_c)
                rolls[adj_c] += 1
                luck -= 1
            elif line[0] == "g":
                break
            else:
                print("Unknown command!")
                continue

        return EncounterActions(
            flee=flee,
            transfers=transfers,
            adjusts=adjusts,
            luck=luck,
            rolls=rolls,
            choices={},
        )

    def _input_encounter_choices(
        self, ch: Character, choices: Choices, rolls: Sequence[int]
    ) -> EncounterActions:
        selections = read_selections(choices, rolls)
        return EncounterActions(
            flee=False,
            transfers=[],
            adjusts=[],
            luck=ch.luck,
            rolls=rolls,
            choices={k: v for k, v in selections.items() if v > 0},
        )

    def _display_records(self, ch: Character, records: List[Record]) -> None:
        if not records:
            return

        for record in records:
            print(render_record(ch, record))

    def _travel(self, dirs: str, ch: Character) -> bool:
        if not dirs:
            print(f"No directions supplied!")
            print()
            return False

        board = self._get(f"/board", Board)

        cubes = {
            CubeCoordinate.from_row_col(hx.coordinate.row, hx.coordinate.column): hx
            for hx in board.hexes
        }
        ch_hex = [hx for hx in board.hexes if hx.name == ch.location][0]
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

        route = []
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
            route.append(cubes[cur].name)

        if len(route) > ch.speed:
            print(f"You have only {ch.speed} speed remaining.")
            print()
            return False

        return self._travel_route(route, ch)

    def _travel_route(self, route: Sequence[str], ch: Character) -> bool:
        for step in route:
            try:
                resp = self._post(
                    f"/play/travel", TravelRequest(step=step), TravelResponse
                )
            except IllegalMoveException as e:
                print(e)
                print()
                return False
            ch = self._get(f"/character", Character)
            if resp.records:
                self._display_records(ch, resp.records)
                print("[Hit return]")
                input()
                return True
            if ch.encounter:
                print(f"Your journey is interrupted in {ch.location}!")
                return True
            elif ch.speed <= 0 and ch.location != route[-1]:
                print(f"You only make it to {ch.location} this turn.")
                return True
        return True

    def _end_turn(self, ch: Character) -> bool:
        try:
            resp = self._post(f"/play/end_turn", EndTurnRequest(), EndTurnResponse)
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        if resp.records:
            self._display_records(ch, resp.records)
            print("[Hit return]")
            input()
            return True
        return True

    def generate_game(self) -> None:
        game_name = self.args.game_name
        json_dir = Path(self.args.json_dir)
        data = generate_game_v2(game_name, json_dir)
        # special handling since player name and game id aren't used
        url = self.base_url + "/game/create"
        request = Request(url, data=serialize(data).encode("utf-8"))
        resp = self._http_common(request, CreateGameResponse)
        print(f"Generated game named {self.args.game_name} (id {resp.game_id})")

    def _get(self, path: str, cls: Type[T]) -> T:
        url = self.base_url
        url += f"/game/{self.args.game_id}/{self.args.name}"
        url += path
        request = Request(url)
        return self._http_common(request, cls)

    def _post(self, path: str, input_val: S, cls: Type[T]) -> T:
        url = self.base_url
        url += f"/game/{self.args.game_id}/{self.args.name}"
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
