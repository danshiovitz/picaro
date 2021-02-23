import re
import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from http.client import HTTPResponse
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
from picaro.server.api_types import (
    Action,
    Board,
    CampRequest,
    CampResponse,
    Character,
    ChoiceType,
    Effect,
    EffectType,
    EncounterEffect,
    Emblem,
    EncounterCheck,
    EncounterActions,
    EncounterOutcome,
    EncounterSingleOutcome,
    EndTurnRequest,
    EndTurnResponse,
    ErrorResponse,
    ErrorType,
    Feat,
    HookType,
    JobRequest,
    JobResponse,
    ResolveEncounterRequest,
    ResolveEncounterResponse,
    TableauCard,
    Token,
    TokenActionRequest,
    TokenActionResponse,
    TravelRequest,
    TravelResponse,
)


S = TypeVar("S")
T = TypeVar("T")


class IllegalMoveException(Exception):
    pass


class BadStateException(Exception):
    pass


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
        parser.set_defaults(cmd=lambda cli: parser.print_help())
        subparsers = parser.add_subparsers()

        get_board_parser = subparsers.add_parser("board")
        get_board_parser.set_defaults(cmd=lambda cli: cli.get_board())
        get_board_parser.add_argument("name", type=str)
        get_board_parser.add_argument("--country", "--countries", action="store_true")
        get_board_parser.add_argument("--region", "--regions", action="store_true")
        get_board_parser.add_argument("--large", action="store_true")
        get_board_parser.add_argument("--center", type=str, default=None)

        get_character_parser = subparsers.add_parser("character")
        get_character_parser.set_defaults(cmd=lambda cli: cli.get_character())
        get_character_parser.add_argument("name", type=str)
        get_character_parser.add_argument("--all", action="store_true")

        play_parser = subparsers.add_parser("play")
        play_parser.set_defaults(cmd=lambda cli: cli.play())
        play_parser.add_argument("name", type=str)
        play_parser.add_argument("--season", action="store_true")

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
        ch = self._get(f"/character/{self.args.name}", Character)
        board = self._get(f"/board/{ch.name}", Board)
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
                body2 = body2[0:4] + hx.region[0]

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

            center_name = self.args.center or board.tokens[0].location
            center_hx = [hx for hx in board.hexes if hx.name == center_name][0]
            for line in render_large(
                set(coords), display, center=center_hx.coordinate, radius=2
            ):
                print(line)

        else:
            for line in self._make_small_map(
                board, show_country=self.args.country, show_region=self.args.region
            ):
                print(line)

        if board.tokens:
            print()
            for tok in board.tokens:
                if tok.type != "City" or len(tok.route) <= 5:
                    print(tok)

        if self.args.country:
            ccount: Dict[str, int] = defaultdict(int)
            for hx in board.hexes:
                ccount[hx.country] += 1
            print(sorted(ccount.items()))

        if self.args.region:
            rcount: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for hx in board.hexes:
                rcount[hx.country][hx.region] += 1
            for ct, rs in rcount.items():
                print(f"{ct}: {sorted(rs.items())}")

    def _make_small_map(
        self,
        board: Board,
        show_country: bool = False,
        show_region: bool = False,
        center: Optional[OffsetCoordinate] = None,
        radius: int = 2,
        encounters: Optional[Set[str]] = None,
    ) -> List[str]:
        coords = {hx.coordinate: hx for hx in board.hexes}

        tokens: Dict[str, List[Token]] = defaultdict(list)
        for tok in board.tokens:
            tokens[tok.location].append(tok)

        def display(coord: OffsetCoordinate) -> str:
            hx = coords[coord]

            if hx.name in tokens:
                if tokens[hx.name][0].type == "Character":
                    return colors.bold + "@" + colors.reset
                elif tokens[hx.name][0].type == "City":
                    return colors.fg.red + "#" + colors.reset
                else:
                    return colors.bold + colors.green + "?" + colors.reset
            elif encounters is not None and hx.name in encounters:
                return colors.bold + colors.bg.red + "!" + colors.reset

            color, symbol = self.terrains[hx.terrain]
            if show_country:
                symbol = hx.country[0]
            elif show_region:
                symbol = hx.region[0]
            return color + symbol + colors.reset

        return render_simple(set(coords), 1, display, center=center, radius=radius)

    def get_character(self) -> None:
        ch = self._get(f"/character/{self.args.name}", Character)
        print(f"{ch.name} ({ch.player_id}) - a {ch.job} [{ch.location}]")
        print(
            f"Health: {ch.health}   Coins: {ch.coins}  Reputation: {ch.reputation} Resources: {ch.resources}   Quest: {ch.quest}"
        )
        print("Skills:")
        for sk, v in sorted(ch.skills.items()):
            if self.args.all or v > 0 or ch.skill_xp[sk] > 0:
                print(f"  {sk}: {v} ({ch.skill_xp[sk]} xp)")
        if not self.args.all:
            print("(Use --all to see all skills)")
        print()
        print("Emblems:")
        for emblem in ch.emblems:
            print(f"* {self._render_emblem(emblem)}")
        if not ch.emblems:
            print("* None")
        print()

    def _render_emblem(self, emblem: Emblem) -> str:
        ret = emblem.name
        if emblem.feats:
            ret += f" ({','.join(self._render_feat(f) for f in emblem.feats)})"
        return ret

    def _render_feat(self, feat: Feat) -> str:
        names = {
            HookType.INIT_SPEED: "speed",
            HookType.INIT_CARD_AGE: "age",
            HookType.INIT_TURNS: "turns",
            HookType.MAX_HEALTH: "health",
            HookType.MAX_LUCK: "luck",
            HookType.MAX_TABLEAU_SIZE: "tableau",
        }
        name = feat.param if feat.param else names.get(feat.hook, feat.hook.name)
        return f"{feat.value:+} {name}"

    def play(self) -> None:
        while True:
            try:
                self._play_turn()
            except BadStateException as e:
                print(e)
                print()
                continue
            ch = self._get(f"/character/{self.args.name}", Character)
            if not self.args.season or ch.remaining_turns <= 0:
                return
            else:
                print("[End of turn, hit return for next]")
                input()
                print("===========")
                print()

    def _play_turn(self) -> None:
        while True:
            ch = self._get(f"/character/{self.args.name}", Character)
            if ch.encounters:
                print()
                self._encounter(ch)
                print()
                continue
            if not ch.acted_this_turn and ch.remaining_turns > 0:
                self._display_play(ch)
                self._input_play_action()
                continue
            return

    def _display_play(self, ch: Character) -> None:
        board = self._get(f"/board/{ch.name}", Board)
        encounters = {card.location for card in ch.tableau}

        ch_hex = [hx for hx in board.hexes if hx.name == ch.location][0]
        minimap = self._make_small_map(
            board, center=ch_hex.coordinate, radius=3, encounters=encounters
        )

        display = []
        display.append(
            f"{ch.name} ({ch.player_id}) - a {ch.job} [{ch.location}, in {ch_hex.country}]"
        )
        display.append("")
        display.append(
            f"Health: {ch.health:2}   Coins: {ch.coins:2}   Reputation: {ch.reputation:2}   Resources: {ch.resources:2}   Quest: {ch.quest:2}"
        )
        if ch.remaining_turns:
            display.append(
                f" Turns: {ch.remaining_turns:2}    Luck: {ch.luck:2}        Speed: {ch.speed:2}"
            )
            display.append("")

            def dist(route) -> str:
                ret = f"- {len(route)} away"
                if len(route) > ch.speed:
                    ret += " (too far)"
                return ret

            for idx, card in enumerate(ch.tableau):
                display.append(
                    f"{ascii_lowercase[idx]}. ({card.age}) {card.name} [{card.location} {dist(card.route)}]:"
                )
                display.append(f"       {self._check_str(card.checks[0], ch)}")

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
        while len(display) < 14:
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
        reward_name = self._render_encounter_effect(check.reward)
        penalty_name = self._render_encounter_effect(check.penalty)
        return (
            f"{check.skill} (1d8{ch.skills[check.skill]:+}) vs {check.target_number} "
            f"({reward_name} / {penalty_name})"
        )

    def _input_play_action(self) -> bool:
        while True:
            ch = self._get(f"/character/{self.args.name}", Character)
            if ch.encounters:
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
                board = self._get(f"/board/{ch.name}", Board)
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
        ch = self._get(f"/character/{self.args.name}", Character)
        # if we didn't make it to the card's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if ch.location != card.location or ch.encounters:
            # return true to force input play method to exit also
            return True

        # otherwise start the main job
        try:
            resp = self._post(
                f"/play/{ch.name}/job",
                JobRequest(card_id=card.id),
                JobResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        return True

    def _token_action(self, token: Token, action: Action, ch: Character) -> bool:
        self._travel_route(token.route, ch)
        ch = self._get(f"/character/{self.args.name}", Character)
        # if we didn't make it to the token's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if ch.location != token.location or ch.encounters:
            # return true to force input play method to exit also
            return True

        # otherwise start the action
        try:
            resp = self._post(
                f"/play/{ch.name}/token_action",
                TokenActionRequest(token=token.name, action=action.name),
                TokenActionResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False

        return True

    def _camp(self, ch: Character) -> bool:
        try:
            resp = self._post(
                f"/play/{ch.name}/camp", CampRequest(rest=True), CampResponse
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        return True

    def _encounter(self, ch: Character) -> bool:
        signs = ", ".join(ch.encounters[0].signs)
        print(f"{ch.encounters[0].name} [signs: {signs}]")
        print(ch.encounters[0].desc)

        return self._input_encounter_action(ch)

    def _input_encounter_action(self, ch: Character) -> bool:
        rolls = list(ch.encounters[0].rolls[:])
        luck = ch.luck
        transfers = []
        adjusts = []
        flee = False
        choice = None

        while True and ch.encounters[0].checks:
            print()
            for idx, check in enumerate(ch.encounters[0].checks):
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

        if not flee and ch.encounters[0].choice_type != ChoiceType.NONE:
            all_choices = ch.encounters[0].choices
            can_choose = (
                len(all_choices) > 1
                and ch.encounters[0].choice_type != ChoiceType.RANDOM
            ) or ch.encounters[0].choice_type == ChoiceType.OPTIONAL
            for idx, choices in enumerate(all_choices):
                pfx = (" " + ascii_lowercase[idx] + ". ") if can_choose else " * "
                line = pfx + ", ".join(self._render_effect(eff) for eff in choices)
                if (
                    ch.encounters[0].choice_type == ChoiceType.RANDOM
                    and ch.encounters[0].rolls[-1] == idx + 1
                ):
                    line = colors.bold + line + colors.reset
                print(line)
            if can_choose:
                if ch.encounters[0].choice_type == ChoiceType.OPTIONAL:
                    print(" q. Do none")
                while True:
                    print("Make your choice: ", end="")
                    line = input().lower().strip()
                    if not line:
                        continue
                    if line[0] == "q":
                        if ch.encounters[0].choice_type == ChoiceType.OPTIONAL:
                            choice = None
                            break
                        else:
                            print("You must make a selection.")
                            continue
                    c_idx = ascii_lowercase.index(line[0])
                    if c_idx >= len(all_choices):
                        print("Not a valid choice?")
                        continue
                    choice = c_idx
                    break
            else:
                if ch.encounters[0].choice_type == ChoiceType.RANDOM:
                    choice = ch.encounters[0].rolls[-1] - 1
                elif len(ch.encounters[0].choices) == 1:
                    choice = 0

        actions = EncounterActions(
            flee=flee,
            transfers=transfers,
            adjusts=adjusts,
            luck=luck,
            rolls=rolls,
            choice=choice,
        )
        try:
            resp = self._post(
                f"/play/{ch.name}/resolve_encounter",
                ResolveEncounterRequest(actions=actions),
                ResolveEncounterResponse,
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        print()
        print(f"The outcome of your encounter:")

        def render_single_int(
            pfx: str, single: Optional[EncounterSingleOutcome[int]]
        ) -> None:
            if single is None:
                return
            if single.new_val > single.old_val:
                print(
                    f"* {pfx} increased to {single.new_val} ({', '.join(single.comments)})."
                )
            elif single.new_val < single.old_val:
                print(
                    f"* {pfx} decreased to {single.new_val} ({', '.join(single.comments)})."
                )
            else:
                print(
                    f"* {pfx} remained at {single.new_val} ({', '.join(single.comments)})."
                )

        render_single_int("Your health has", resp.outcome.health)
        render_single_int("Your coins have", resp.outcome.coins)
        render_single_int("Your reputation has", resp.outcome.reputation)
        for sk, val in resp.outcome.xp.items():
            render_single_int(f"Your {sk} xp has", val)
        render_single_int("Your resources have", resp.outcome.resources)
        render_single_int("Your quest points have", resp.outcome.quest)
        render_single_int("Your remaining turns have", resp.outcome.turns)
        render_single_int("Your speed has", resp.outcome.speed)
        if resp.outcome.transport_location is not None:
            tl = resp.outcome.transport_location
            print(f"* You are now in hex {tl.new_val} ({', '.join(tl.comments)}).")
        if resp.outcome.new_job is not None:
            nj = resp.outcome.new_job
            print(f"* You have become a {nj.new_val} ({', '.join(nj.comments)})!")

        return True

    def _render_encounter_effect(self, eff: EncounterEffect) -> str:
        names = {
            EncounterEffect.NOTHING: "nothing",
            EncounterEffect.GAIN_COINS: "+coins",
            EncounterEffect.GAIN_XP: "+xp",
            EncounterEffect.GAIN_REPUTATION: "+reputation",
            EncounterEffect.GAIN_HEALING: "+healing",
            EncounterEffect.GAIN_RESOURCES: "+resources",
            EncounterEffect.GAIN_QUEST: "+quest",
            EncounterEffect.GAIN_TURNS: "+turns",
            EncounterEffect.LOSE_COINS: "-coins",
            EncounterEffect.LOSE_REPUTATION: "-reputation",
            EncounterEffect.DAMAGE: "-damage",
            EncounterEffect.LOSE_RESOURCES: "-resources",
            EncounterEffect.LOSE_TURNS: "-turns",
            EncounterEffect.LOSE_SPEED: "-speed",
            EncounterEffect.DISRUPT_JOB: "-job",
            EncounterEffect.TRANSPORT: "-transport",
        }
        return names.get(eff, eff.name)

    def _render_effect(self, eff: Effect) -> str:
        def _with_s(word: str, word_s: Optional[str] = None) -> str:
            if eff.value == 1 or eff.value == -1:
                return f"{eff.value:+} {word}"
            elif word_s is None:
                return f"{eff.value:+} {word}s"
            else:
                return f"{eff.value:+} {word_s}"

        if eff.type == EffectType.MODIFY_COINS:
            return _with_s("coin")
        elif eff.type == EffectType.MODIFY_XP:
            return f"{eff.value:+} {eff.param} xp"
        elif eff.type == EffectType.MODIFY_REPUTATION:
            return f"{eff.value:+} reputation"
        elif eff.type == EffectType.MODIFY_HEALTH:
            return f"{eff.value:+} health"
        elif eff.type == EffectType.MODIFY_RESOURCES:
            return _with_s("resource")
        elif eff.type == EffectType.MODIFY_QUEST:
            return f"{eff.value:+} quest"
        elif eff.type == EffectType.MODIFY_TURNS:
            return _with_s("turn")
        elif eff.type == EffectType.MODIFY_SPEED:
            return f"{eff.value:+} speed"
        elif eff.type == EffectType.DISRUPT_JOB:
            return f"rank-{eff.value:+} job turmoil"
        elif eff.type == EffectType.TRANSPORT:
            return f"rank-{eff.value:+} random transport"
        else:
            return eff

    def _travel(self, dirs: str, ch: Character) -> bool:
        if not dirs:
            print(f"No directions supplied!")
            print()
            return False

        board = self._get(f"/board/{ch.name}", Board)

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
                    f"/play/{ch.name}/travel", TravelRequest(step=step), TravelResponse
                )
            except IllegalMoveException as e:
                print(e)
                print()
                return False
            ch = self._get(f"/character/{self.args.name}", Character)
            if ch.encounters:
                print(f"Your journey is interrupted in {ch.location}!")
                return True
            elif ch.speed <= 0 and ch.location != route[-1]:
                print(f"You only make it to {ch.location} this turn.")
                return True
        return True

    def _end_turn(self, ch: Character) -> bool:
        try:
            resp = self._post(
                f"/play/{ch.name}/end_turn", EndTurnRequest(), EndTurnResponse
            )
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        return True

    def _get(self, path: str, cls: Type[T]) -> T:
        url = self.base_url
        url += f"/game/{self.args.game_id}"
        url += path
        request = Request(url)
        return self._http_common(request, cls)

    def _post(self, path: str, input_val: S, cls: Type[T]) -> T:
        url = self.base_url
        url += f"/game/{self.args.game_id}"
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
