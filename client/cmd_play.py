import sys
from collections import defaultdict
from string import ascii_lowercase
from typing import Any, Callable

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.hexmap.display import CubeCoordinate
from picaro.server.api_types import *
from .read import ReadClientBase


class PlayCommand:
    def add_command(self, subparsers: Any) -> None:  # Any -> add_subparsers retval
        play_parser = subparsers.add_parser("play")
        play_parser.set_defaults(cmd=lambda cli: self.play(cli))
        play_parser.add_argument("--season", action="store_true")

    def play(self, client: ReadClientBase) -> None:
        runner = PlayRunner(client)
        runner.run()


class PlayRunner:
    def __init__(self, client: ReadClientBase) -> None:
        self.client = client

    def run(self) -> None:
        while True:
            try:
                self._play_turn()
            except BadStateException as e:
                print(e)
                print()
                continue
            ch = client.character
            if not self.args.season or ch.remaining_turns <= 0:
                return
            else:
                print("===========")
                print()

    def _play_turn(self) -> None:
        while True:
            ch = self.client.character
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
                input_callbacks = self._display_play()
                self._input_play_action(input_callbacks)
                continue
            self._display_play(ch)
            return

    def _display_play(self) -> Dict[str, Callable[[str], List[Record]]]:
        ch = self.client.character
        ch_hex = self.client.hexes.get_by_name(ch.location)
        minimap = self.client.render_small_map(
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
            input_callbacks: Dict[str, Callable[[str], List[Record]]] = {}

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
    ) -> Tuple[List[str], Dict[str, Callable[[str], List[Record]]]]:
        lines: List[str] = []
        inputs: Dict[str, Callable[[str], List[Record]]] = {}

        full_list: List[Tuple[List[str], Callable[[str], List[Record]]]] = []

        for card in ch.tableau:
            # can't save card in lambda because it gets reassigned
            callback = lambda _, uuid=card.uuid, route=card.route: self._job(
                uuid, route
            )
            titles = [f"({card.age}) {card.name} [{self.client.render_route(card.route)}]:"]
            if card.type == FullCardType.CHALLENGE:
                titles.append(f"       {self.client.render_check(card.data[0])}")
            else:
                titles.append("")
            full_list.append((titles, callback))

        actions = list(self.client.get_actions())

        def route_sort(route):
            if route.type == RouteType.GLOBAL:
                return 1001
            elif route.type == RouteType.UNAVAILABLE:
                return 1002
            else:
                return len(route.steps)

        actions.sort(key=lambda v: (route_sort(v.route), v.name, v.uuid))

        for action in actions:
            # can't save action in lambda because it gets reassigned
            callback = (
                lambda _, uuid=action.uuid, route=action.route: self._perform_action(
                    uuid, route
                )
            )
            titles = [f"{action.name} [{self.client.render_route(action.route)}]"]
            full_list.append((titles, callback))

        idx = 0
        max_idx = 9
        for titles, callback in full_list[:max_idx]:
            bullet = ascii_lowercase[idx]
            lines.append(f"{bullet}. {titles[0]}")
            for t in titles[1:]:
                lines.append(t)
            inputs[bullet] = callback
            idx += 1

        if len(full_list) > max_idx:
            bullet = ascii_lowercase[max_idx]
            lines.append(f"{bullet}. ...")
            inputs[bullet] = lambda _: self._input_extended(full_list)

        lines.append("q. Quit")
        inputs["q"] = lambda _: self._quit()
        lines.append("t. Travel (uio.jkl)")
        inputs["t"] = lambda d: self._travel(d, ch.location, ch.speed)
        lines.append("x. Camp")
        inputs["x"] = lambda _: self._camp()
        lines.append("z. End Turn (if you don't want to do a job or camp)")
        inputs["z"] = lambda _: self._end_turn()

        return lines, inputs

    def _input_extended(
        self, full_list: List[Tuple[List[str], Callable[[str], List[Record]]]]
    ) -> List[Record]:
        idx = 1
        for titles, callback in full_list:
            print(f"{idx}. {titles[0]}")
            for t in titles[1:]:
                print(t)
            idx += 1
        print("q. Quit")

        while True:
            print("Action? ", end="")
            line = input().lower().strip()
            if not line:
                continue
            bits = (line + " ").split(" ", 1)
            if bits[0] == "q":
                raise IllegalMoveException("...")

            try:
                val = int(bits[0])
            except ValueError:
                print("Unknown input")
                continue
            if val < 1 or val > len(full_list):
                print("Unknown action")
                continue
            return full_list[val - 1][1](bits[1].strip())

    def _input_play_action(
        self, input_callbacks: Dict[str, Callable[[str], List[Record]]]
    ) -> None:
        while True:
            ch = self.client.character
            if ch.encounter:
                return
            print("Action? ", end="")
            line = input().lower().strip()
            if not line:
                continue
            bits = (line + " ").split(" ", 1)
            if bits[0] not in input_callbacks:
                print("Unknown action")
                print()
                continue

            try:
                records = input_callbacks[bits[0]](bits[1].strip())
                break
            except IllegalMoveException as e:
                # if this is from the extended-menu, break out so it reprints
                # the full input:
                if str(e) == "...":
                    return
                print(e)
                print()
                continue

        if records:
            ch = self.client.character
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
        return self.client.do_job(card_uuid)

    def _perform_action(self, action_uuid: str, route: Route) -> Sequence[Record]:
        # if we didn't make it to the action's location uneventfully,
        # then exit to let the player deal with the encounter and
        # perhaps then make another choice for their main action
        if not self._travel_route(route):
            return []

        # otherwise start the action
        return self.client.perform_action(action_uuid)

    def _quit(self) -> None:
        print("Bye!")
        sys.exit(0)

    def _travel(self, dirs: str, start_loc: str, speed: int) -> Sequence[Record]:
        if not dirs:
            print(f"No directions supplied!")
            print()
            return []

        hexes = self.client.hexes.get_all()
        cubes = {
            CubeCoordinate.from_row_col(hx.coordinate.row, hx.coordinate.column): hx
            for hx in hexes
        }
        ch_hex = [hx for hx in hexes if hx.name == start_loc][0]
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
        return self.client.camp()

    def _end_turn(self) -> Sequence[Record]:
        return self.client.end_turn()

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
            commands = self._input_encounter_checks(
                ch, ch.encounter.uuid, ch.encounter.data, ch.encounter.rolls
            )
        elif ch.encounter.type == EncounterType.CHOICE:
            commands = self._input_encounter_choices(
                ch, ch.encounter.uuid, ch.encounter.data, ch.encounter.rolls
            )
        else:
            raise Exception("Encounter with no checks or choices?")

        try:
            records = self.client.resolve_encounter(commands)
        except IllegalMoveException as e:
            print(e)
            print()
            return False
        print()
        print("The outcome of your encounter:")
        self._display_records(ch, records)
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
                    f"Check #{idx+1}: {self.client.render_check(check)}: {rolls[idx]} - {status}"
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
        selections = self.client.read_selections(choices, rolls)
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
            print(self.client.render_record(ch, record))

    def _travel_route(self, route: Route) -> bool:
        if route.type == RouteType.GLOBAL:
            return True
        elif route.type == RouteType.UNAVAILABLE:
            print(f"There's no obvious way to get there.")
            return False

        for step in route.steps:
            records = self.client.travel(step)

            ch = self.client.character
            # if there are records, display but keep walking:
            if records:
                self._display_records(ch, records)
                print("[Hit return]")
                input()

            if ch.encounter:
                print(f"Your journey is interrupted in {ch.location}!")
                return False
            elif ch.speed <= 0 and ch.location != route.steps[-1]:
                print(f"You only make it to {ch.location} this turn.")
                return False
        return True
