import re
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from string import ascii_lowercase
from typing import List, Optional, Set, Type, TypeVar
from urllib.request import HTTPErrorProcessor, Request, build_opener, urlopen

from picaro.client.colors import colors
from picaro.common.hexmap.display import CubeCoordinate, DisplayInfo, OffsetCoordinate, render_simple, render_large
from picaro.common.serializer import deserialize, serialize
from picaro.server.api_types import Board, CampRequest, CampResponse, CardPreview, Character, EncounterCheck, EncounterActions, ErrorResponse, ErrorType, StartEncounterRequest, StartEncounterResponse, ResolveEncounterRequest, ResolveEncounterResponse, TravelRequest, TravelResponse


S = TypeVar("S")
T = TypeVar("T")


class IllegalMoveException(Exception):
    pass


class BadStateException(Exception):
    pass


class NonThrowingHTTPErrorProcessor(HTTPErrorProcessor):
    def http_response(self, request, response):
        return response


class Client:
    @classmethod
    def run(cls) -> None:
        args = cls.parse_args()
        client = Client(args)
        client.args.cmd(client)

    @classmethod
    def parse_args(cls) -> None:
        parser = ArgumentParser()
        parser.add_argument("--host", type=str, default="http://localhost:8080")
        parser.set_defaults(cmd=lambda cli: parser.print_help())
        subparsers = parser.add_subparsers()

        get_board_parser = subparsers.add_parser("board")
        get_board_parser.set_defaults(cmd=lambda cli: cli.get_board())
        get_board_parser.add_argument('--country', '--countries', action='store_true')
        get_board_parser.add_argument('--large', action='store_true')
        get_board_parser.add_argument('--center', type=str, default=None)

        get_character_parser = subparsers.add_parser("character")
        get_character_parser.set_defaults(cmd=lambda cli: cli.get_character())
        get_character_parser.add_argument('name', type=str)

        play_parser = subparsers.add_parser("play")
        play_parser.set_defaults(cmd=lambda cli: cli.play())
        play_parser.add_argument('name', type=str)
        play_parser.add_argument('--season', action='store_true')

        return parser.parse_args()

    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.base_url = self.args.host
        if self.base_url and self.base_url[-1] == "/":
            self.base_url = self.base_url[:-1]
        self.terrains = {
            "Forest": (colors.fg.green, "\""),
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
        board = self._get("/board", Board)
        coords = {
            hx.coordinate: hx for hx in board.hexes
        }

        tokens = defaultdict(list)
        for tok in board.tokens:
            tokens[tok.location].append(tok)

        if self.args.large:
            def display(coord: OffsetCoordinate) -> DisplayInfo:
                hx = coords[coord]
                # return self.terrains[hx.terrain][0] + hx.country[0] + colors.reset
                color, symbol = self.terrains[hx.terrain]
                body1 = hx.name + " "
                body2 = (hx.country + "     ")[0:5]

                if hx.name in tokens:
                    body2 = colors.bold + (tokens[hx.name][0].name + "     ")[0:5] + colors.reset
                return DisplayInfo(
                    fill=color + symbol + colors.reset,
                    body1=body1,
                    body2=body2,
                )

            center_hx = [hx for hx in board.hexes if hx.name == board.tokens[0].location][0]
            for line in render_large(set(coords), display, center=center_hx.coordinate, radius=2):
                print(line)

        else:
            for line in self._make_small_map(board, self.args.country):
                print(line)

        if board.tokens:
            print()
            for tok in board.tokens:
                print(tok)

    def _make_small_map(self, board: Board, show_country: bool, center: Optional[OffsetCoordinate] = None, radius: int = 2, encounters: Optional[Set[str]] = None) -> List[str]:
        coords = {
            hx.coordinate: hx for hx in board.hexes
        }

        tokens = defaultdict(list)
        for tok in board.tokens:
            tokens[tok.location].append(tok)

        if not encounters:
            encounters = set()

        def display(coord: OffsetCoordinate) -> str:
                hx = coords[coord]

                if hx.name in tokens:
                    return colors.bold + "@" + colors.reset
                elif hx.name in encounters:
                    return colors.bold + colors.bg.red + "!" + colors.reset

                color, symbol = self.terrains[hx.terrain]
                return (
                    color +
                    (hx.country[0] if show_country else symbol) +
                    colors.reset
                )

        return render_simple(set(coords), 1, display, center=center, radius=radius)

    def get_character(self) -> None:
        ch = self._get(f"/character/{self.args.name}", Character)
        print(f"{ch.name} ({ch.player_id}) - a {ch.job}")
        print(f"Health: {ch.health}   Coins: {ch.coins}  Reputation: {ch.reputation} Resources: {ch.resources}")
        print("Skills:")
        for sk, v in sorted(ch.skills.items()):
            print(f"  {sk}: {v}")
        print()

    def play(self) -> None:
        while True:
            try:
                board = self._get("/board", Board)
                ch = self._get(f"/character/{self.args.name}", Character)
                self._display_play(board, ch)
                if not ch.tableau or ch.tableau.remaining_turns == 0:
                    return
                if ch.tableau.encounter:
                    self._do_encounter(None, board, ch)
                else:
                    self._input_play_action(board, ch)
                if not self.args.season:
                    return
                else:
                    print()
                    print("===========")
                    print()
            except BadStateException as e:
                print(e)
                continue


    def _display_play(self, board: Board, ch: Character) -> None:
        encounters = {card.location_name for card in ch.tableau.cards} if ch.tableau else None

        ch_hex = [hx for hx in board.hexes if hx.name == ch.hex][0]
        minimap = self._make_small_map(board, False, center=ch_hex.coordinate, radius=3, encounters=encounters)

        display = []
        display.append(f"{ch.name} ({ch.player_id}) - a {ch.job} [{ch.location}, in {ch_hex.country}]")
        display.append("")
        display.append(f"Health: {ch.health:2}   Coins: {ch.coins:2}   Reputation: {ch.reputation:2}   Resources: {ch.resources:2}   Quest: {ch.quest:2}")
        if ch.tableau:
            display.append(f" Turns: {ch.tableau.remaining_turns:2}    Luck: {ch.tableau.luck:2}")
            display.append("")
            for idx, card in enumerate(ch.tableau.cards):
                pc_skill = f""
                cs = (f"{ascii_lowercase[idx]}. ({card.age}) {card.name}:"
                      f" {self._check_str(card.checks[0], ch)} [{card.location_name}]")
                display.append(cs)
            display.append("t. Travel (uio.jkl)")
            display.append("x. Camp")
        while len(display) < 14:
            display.append("")

        pad = lambda val, width: val + " " * (width - len(val))
        display = [pad(display[idx], 80) + (minimap[idx] if idx < len(minimap) else "")
                  for idx in range(len(display))]
        while display[-1].strip() == "":
            display.pop()

        for line in display:
            print(line)
        print()

    def _check_str(self, check: EncounterCheck, ch: Character) -> str:
        return (f"{check.skill} (1d8{ch.skills[check.skill]:+}) vs {check.target_number} "
                f"(+{check.reward.name.lower()}, -{check.penalty.name.lower()})")

    def _input_play_action(self, board: Board, ch: Character) -> None:
        while True:
            print("Action? ", end="")
            line = input().lower()
            if line[0] in "abcde":
                c_idx = "abcde".index(line[0])
                if c_idx < len(ch.tableau.cards):
                    if self._do_encounter(ch.tableau.cards[c_idx], board, ch):
                        return
                else:
                    print("No such encounter card!")
                    print()
                    continue
            elif line[0] == "t":
                ww = re.split(r"\s+", line, 2)
                dirs = None if len(ww) == 1 else ww[1]
                if not dirs or any(d not in "uio.jkl" for d in dirs):
                    print("travel <dirs> - uio.jkl")
                    print()
                    continue
                if len(dirs) > 3:
                    print("max 3 steps")
                    print()
                    continue
                if self._do_travel(dirs, board, ch):
                    return
            elif line[0] == "x":
                if self._do_camp(board, ch):
                    return
            else:
                print("Unknown action")
                print()
                continue

    def _do_encounter(self, card_preview: Optional[CardPreview], board: Board, ch: Character) -> bool:
        if not ch.tableau.encounter and card_preview is not None:
            try:
                resp = self._post(f"/play/{ch.name}/encounter/start", StartEncounterRequest(card_id=card_preview.id), StartEncounterResponse)
            except IllegalMoveException as e:
                print(e)
                return False
            # ok, so encounter started - re-request the character to get
            # the full details from the tableau:
            ch = self._get(f"/character/{self.args.name}", Character)

        signs = ", ".join(ch.tableau.encounter.card.signs)
        print(f"{ch.tableau.encounter.card.template.name} [signs: {signs}]")
        print(ch.tableau.encounter.card.template.desc)

        self._input_encounter_action(board, ch)
        return True

    def _input_encounter_action(self, board: Board, ch: Character) -> None:
        rolls = ch.tableau.encounter.rolls[:]
        luck = ch.tableau.luck
        transfers = []
        adjusts = []
        flee = False

        while True:
            print()
            for idx, check in enumerate(ch.tableau.encounter.card.checks):
                status = "SUCCESS" if rolls[idx] >= check.target_number else "FAILURE"
                print(f"Check #{idx+1}: {self._check_str(check, ch)}: {rolls[idx]} - {status}")
            print("You can go, transfer, adjust, or flee: ", end="")
            line = input().lower()
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

        actions = EncounterActions(flee=flee, transfers=transfers, adjusts=adjusts, luck=luck, rolls=rolls)
        try:
            resp = self._post(f"/play/{ch.name}/encounter/resolve", ResolveEncounterRequest(actions=actions), ResolveEncounterResponse)
        except IllegalMoveException as e:
            print(e)
            return False
        print(f"You have encountered: {resp.outcome}!")
        return True


    def _do_travel(self, dirs: str, board: Board, ch: Character) -> bool:
        cubes = {CubeCoordinate.from_row_col(hx.coordinate.row, hx.coordinate.column): hx for hx in board.hexes}
        ch_hex = [hx for hx in board.hexes if hx.name == ch.hex][0]
        cur = CubeCoordinate.from_row_col(ch_hex.coordinate.row, ch_hex.coordinate.column)

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
            xm, ym, zm = dir_map[d]
            cur = cur.step(xm, ym, zm)
            route.append(cubes[cur].name)

        try:
            resp = self._post(f"/play/{ch.name}/travel", TravelRequest(route=route), TravelResponse)
        except IllegalMoveException as e:
            print(e)
            return False
        print("You arrive!")
        ch = self._get(f"/character/{self.args.name}", Character)
        return self._do_encounter(None, board, ch)

    def _do_camp(self, board: Board, ch: Character) -> bool:
        try:
            resp = self._post(f"/play/{ch.name}/camp", CampRequest(rest=True), CampResponse)
        except IllegalMoveException as e:
            print(e)
            return False
        print("You feel refreshed!")
        return True

    def _get(self, path: str, cls: Type[T]) -> T:
        url = self.base_url
        url += path
        request = Request(url)
        return self._http_common(request, cls)

    def _post(self, path: str, input_val: S, cls: Type[T]) -> T:
        url = self.base_url
        url += path
        request = Request(url, data=serialize(input_val).encode("utf-8"))
        return self._http_common(request, cls)

    def _http_common(self, request: Request, cls: Type[T]) -> T:
        with self.opener.open(request) as response:
            data = response.read().decode("utf-8")
        if response.status == 200:
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
    args = parse_args()
    args.cmd(args)
