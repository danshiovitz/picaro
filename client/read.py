import curses
import curses.textpad
import re
from collections import defaultdict
from string import ascii_lowercase
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar

from picaro.common.exceptions import IllegalMoveException
from picaro.server.api_types import *

from .render import RenderClientBase


T = TypeVar("T")


class ReadClientBase(RenderClientBase):
    def read_text(self, prompt: str, textbox: bool = False) -> str:
        if not textbox:
            print(prompt + " ", end="")
            return input().strip()

        def enter_msg(stdscr):
            stdscr.addstr(0, 0, f"{prompt} (hit Ctrl-G to send)")

            editwin = curses.newwin(5, 30, 2, 1)
            curses.textpad.rectangle(stdscr, 1, 0, 1 + 5 + 1, 1 + 30 + 1)
            stdscr.refresh()

            box = curses.textpad.Textbox(editwin, insert_mode=True)

            # Let the user edit until Ctrl-G is struck.
            box.edit()

            # Get resulting contents
            message = box.gather()
            return message

        msg = curses.wrapper(enter_msg)
        return msg.strip()

    # > modify coins +1
    # > delete a
    # > create project
    # What's the name of the project? Find the magic wand
    # What's the type? Monument
    # What's the start hex? AE12
    # What should the next stage be? (discovery, waiting, challenge, resource, random, done)
    #   discovery start=AD12
    # > add emblem
    # What's the name of the emblem? Lord of the Hats
    # What overlays does the emblem provide?
    # > modify search skill +1
    # > done

    def read_effects(
        self,
        prompt: str,
        init: List[Effect],
    ) -> List[Effect]:
        skills = self.skills.get_all()
        resources = self.resources.get_all()
        job_names = [j.name for j in self.jobs.get_all()]
        hexes = [h.name for h in self.hexes.get_all()]
        fixup = lambda v: (v[0], True, v[1])
        effect_choices = [
            (
                "Modify coins <amount>",
                lambda ln: self._lparse_effect(EffectType.MODIFY_COINS, ln),
            ),
            (
                "Modify xp <amount> <skill or 'free'>",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_XP, ln, subtypes=skills, none_type="free"
                ),
            ),
            (
                "Modify reputation <amount>",
                lambda ln: self._lparse_effect(EffectType.MODIFY_REPUTATION, ln),
            ),
            (
                "Modify health <amount>",
                lambda ln: self._lparse_effect(EffectType.MODIFY_HEALTH, ln),
            ),
            (
                "Modify resources <amount> <resource or 'draw'>",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_RESOURCES,
                    ln,
                    subtypes=resources,
                    none_type="draw",
                ),
            ),
            (
                "Modify turns <amount>",
                lambda ln: self._lparse_effect(EffectType.MODIFY_TURNS, ln),
            ),
            (
                "Use up activity",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_ACTIVITY,
                    ln,
                    lparse_val=lambda ln: (-1, True, ln),
                ),
            ),
            (
                "Refresh activity",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_ACTIVITY,
                    ln,
                    lparse_val=lambda ln: (1, True, ln),
                ),
            ),
            (
                "Move to location <hex>",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_LOCATION,
                    ln,
                    lparse_val=lambda ln: fixup(
                        self._lparse_fixedstr("hex", ln, hexes)
                    ),
                ),
            ),
            (
                "Switch to job <job>",
                lambda ln: self._lparse_effect(
                    EffectType.MODIFY_JOB,
                    ln,
                    lparse_val=lambda ln: fixup(
                        self._lparse_fixedstr("job", ln, job_names)
                    ),
                ),
            ),
            (
                "Add emblem <name>",
                lambda ln: self._lparse_effect(
                    EffectType.ADD_EMBLEM,
                    ln,
                    lparse_val=lambda ln: fixup(self._lparse_gadget(ln)),
                ),
            ),
            (
                "Queue encounter",
                lambda ln: self._lparse_effect(
                    EffectType.QUEUE_ENCOUNTER,
                    ln,
                    lparse_val=lambda ln: fixup(self._lparse_template_card(ln)),
                ),
            ),
            (
                "Random transport <distance>",
                lambda ln: self._lparse_effect(EffectType.TRANSPORT, ln),
            ),
            (
                "Leadership challenge <difficulty>",
                lambda ln: self._lparse_effect(EffectType.LEADERSHIP, ln),
            ),
        ]

        return self._read_complex(
            prompt, init, effect_choices, lambda e: self.render_effect(e)
        )

    def read_overlays(
        self,
        prompt: str,
        init: List[Overlay],
    ) -> List[Overlay]:
        skills = self.skills.get_all()
        overlay_choices = [
            (
                "Modify init tableau age <amount>",
                lambda ln: self._lparse_overlay(OverlayType.INIT_TABLEAU_AGE, ln),
            ),
            (
                "Modify init turns <amount>",
                lambda ln: self._lparse_overlay(OverlayType.INIT_TURNS, ln),
            ),
            (
                "Modify max health <amount>",
                lambda ln: self._lparse_overlay(OverlayType.MAX_HEALTH, ln),
            ),
            (
                "Modify max luck <amount>",
                lambda ln: self._lparse_overlay(OverlayType.MAX_LUCK, ln),
            ),
            (
                "Modify max tableau size <amount>",
                lambda ln: self._lparse_overlay(OverlayType.MAX_TABLEAU_SIZE, ln),
            ),
            (
                "Modify skill rank <amount> <skill>",
                lambda ln: self._lparse_overlay(
                    OverlayType.SKILL_RANK, ln, subtypes=skills
                ),
            ),
            (
                "Modify skill reliability <amount> <skill>",
                lambda ln: self._lparse_overlay(
                    OverlayType.RELIABLE_SKILL, ln, subtypes=skills
                ),
            ),
            (
                "Modify init speed <amount>",
                lambda ln: self._lparse_overlay(OverlayType.INIT_SPEED, ln),
            ),
            (
                "Modify resource limit <amount>",
                lambda ln: self._lparse_overlay(OverlayType.MAX_RESOURCES, ln),
            ),
        ]

        return self._read_complex(prompt, init, overlay_choices, self.render_overlay)

    def _read_complex(
        self,
        prompt: str,
        init: List[T],
        choice_list: List[Tuple[str, Callable[[str], Tuple[T, str]]]],
        render_func: Callable[[T], str],
    ) -> List[T]:
        print(prompt)
        items = init[:]
        while True:
            if items:
                print()
                print("Current items:")
                for item in items:
                    print(f"* {render_func(item)}")
                print()

            for idx, (desc, fn) in enumerate(choice_list):
                print(f" {ascii_lowercase[idx]}. {desc}")
            print(" q. Cancel")
            print(" z. Finish")
            print("Make your choice: ", end="")

            line = input().strip()
            if not line:
                continue
            choice_m = re.match(r"^([0-9]+|[a-z])(?:\s+(-?[0-9]+))?", line)
            if not choice_m:
                print("Invalid input?")
                continue
            choice_v = choice_m.group(1).lower()
            line = line[len(choice_v) :].strip()
            if choice_v == "q":
                raise IllegalMoveException("Cancelled")
            if choice_v == "z":
                return items
            choice_idx = ascii_lowercase.find(choice_v)
            if choice_idx < 0 or choice_idx >= len(choice_list):
                print("Not a valid choice?")
                continue
            try:
                item, line = choice_list[choice_idx][1](line)
                if line:
                    raise IllegalMoveException(f"Unparsed: {line}")
                items.append(item)
            except IllegalMoveException as e:
                print(e)
                continue

    def _parse_or_prompt(self, name: str, regex_str: str, line: str) -> Tuple[str, str]:
        rex = re.compile(regex_str)
        m = rex.match(line)
        if m:
            val = m.group(0)
            line = line[len(val) :].strip()
            return val, line
        if line:
            raise IllegalMoveException(f"Invalid value for {name}: {line}")
        while True:
            entered = read_text(f"Enter {name}:", textbox=False)
            if not entered:
                continue
            m = rex.match(entered)
            if m and m.group(0) == entered:
                return entered, ""
            raise IllegalMoveException(f"Invalid value for {name}: {entered}")

    def _lparse_int(self, name: str, line: str) -> Tuple[int, bool, str]:
        val_str, line = self._parse_or_prompt(name, r"(=?(?:\+|-)?[0-9]+)", line)
        is_absolute = False
        if val_str[0] == "=":
            is_absolute = True
            val_str = val_str[1:]
        try:
            return int(val_str), is_absolute, line
        except ValueError as e:
            raise IllegalMoveException(f"Bad {name}: {e}")

    def _lparse_str(self, name: str, line: str) -> Tuple[str, str]:
        return self._parse_or_prompt(name, r"(.+)", line)

    def _lparse_fixedstr(
        self,
        name: str,
        line: str,
        choices: Sequence[str],
        none_type: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        st_str, line = self._parse_or_prompt(name, r"(\S+|\"[^\"]+\")", line)
        if st_str and st_str[0] == '"' and st_str[-1] == '"':
            st_str = st_str[1:-1]
        st_str = st_str.lower()
        st_matches = [st for st in choices if st.lower().startswith(st_str)]

        def strc(items: Sequence[str]) -> str:
            if len(items) == 0:
                return "<no matches>"
            elif len(items) > 10:
                return ", ".join(items[:10]) + ", ..."
            else:
                return ", ".join(items)

        if st_matches:
            if len(st_matches) > 1:
                raise IllegalMoveException(f"Ambiguous: {strc(st_matches)}")
            return st_matches[0], line
        elif none_type and none_type.lower().startswith(st_str):
            return None, line
        else:
            raise IllegalMoveException(f"Unknown {name} {st_str} - {strc(choices)}")

    def _lparse_effect(
        self,
        effect_type: EffectType,
        line: str,
        lparse_val: Optional[Callable[[str], Tuple[Any, bool]]] = None,
        subtypes: Optional[Sequence[str]] = None,
        none_type: Optional[str] = None,
    ) -> Tuple[Effect, str]:
        if lparse_val is None:
            lparse_val = lambda ln: self._lparse_int("amount", ln)

        val, is_absolute, line = lparse_val(line)
        if subtypes:
            subtype, line = self._lparse_fixedstr("subtype", line, subtypes, none_type)
        else:
            subtype = None
        return (
            Effect(
                type=effect_type,
                subtype=subtype,
                value=val,
                is_absolute=is_absolute,
            ),
            line,
        )

    def _lparse_gadget(
        self,
        line: str,
    ) -> Tuple[Gadget, str]:
        name, line = self._lparse_str("name", line)
        overlays = self.read_overlays("Enter overlays for this gadget:", [])
        return Gadget(name, overlays), line

    def _lparse_overlay(
        self,
        overlay_type: OverlayType,
        line: str,
        subtypes: Optional[Sequence[str]] = None,
        none_type: Optional[str] = None,
    ) -> Tuple[Effect, str]:
        val, _, line = self._lparse_int("amount", line)
        if subtypes:
            subtype, line = self._lparse_fixedstr("subtype", line, subtypes, none_type)
        else:
            subtype = None
        return (
            Overlay(
                type=overlay_type,
                value=val,
                subtype=subtype,
            ),
            line,
        )

    def read_selections(self, choices: Choices) -> Dict[int, int]:
        selections = defaultdict(int)
        can_choose = True
        if choices.min_choices >= sum(c.max_choices for c in choices.choice_list):
            for idx, c in enumerate(choices.choice_list):
                selections[idx] = c.max_choices
            can_choose = False

        while True:
            if choices.effects or choices.costs:
                line = " ** Overall: " + ", ".join(
                    self.render_effect(eff) for eff in choices.effects + choices.costs
                )
                print(line)
            selected = 0
            for idx, choice in enumerate(choices.choice_list):
                line = " "
                if can_choose:
                    if len(choices.choice_list) < 15:
                        line += ascii_lowercase[idx] + ". "
                    else:
                        line += str(idx + 1) + ". "
                else:
                    line += "* " if idx in selections else "- "

                line += ", ".join(
                    self.render_effect(eff)
                    for eff in list(choice.effects) + list(choice.costs)
                )
                line += f" [{selections[idx]}/{choice.max_choices}]"
                selected += selections[idx]
                print(line)

            if not can_choose:
                break

            inline = "Make your choice"

            if choices.min_choices != 1 or choices.max_choices != 1:
                print(" z. Finish")
                if choices.min_choices == choices.max_choices:
                    inline += f" ({choices.min_choices} items"
                else:
                    inline += f" ({choices.min_choices}-{choices.max_choices} items"
                if choices.max_choices < 100:
                    inline += f", {choices.max_choices - selected} remaining"
                inline += ")"
            inline += ": "
            print(inline, end="")

            line = input().lower().strip()
            if not line:
                continue
            if line[0] == "z":
                if sum(selections.values()) >= choices.min_choices:
                    break
                else:
                    print("You must make another selection.")
                    continue
            choice_m = re.match(r"^([0-9]+|[a-z])(?:\s+(-?[0-9]+))?", line)
            if not choice_m:
                print("Invalid input?")
                continue
            c_idx = ascii_lowercase.find(choice_m.group(1))
            if c_idx == -1:
                c_idx = int(choice_m.group(1)) - 1
            c_val = int(choice_m.group(2)) if choice_m.group(2) else None
            if c_idx < 0 or c_idx >= len(choices.choice_list):
                print("Not a valid choice?")
                continue
            if c_val is None:
                # if this is a once-only choice, then entering the choice with no
                # count toggles, otherwise it always adds 1
                if choices.choice_list[c_idx].max_choices == 1 and selections[c_idx]:
                    c_val = -1
                else:
                    c_val = 1
            cc = choices.choice_list[c_idx]
            if selections[c_idx] + c_val < cc.min_choices:
                print(
                    f"That would be lower than the allowed minimum ({cc.min_choices}) for the choice."
                )
                continue
            if selections[c_idx] + c_val > cc.max_choices:
                print(
                    f"That would be higher than the allowed maximum ({cc.max_choices}) for the choice."
                )
                continue
            selections[c_idx] += c_val

            if sum(selections.values()) >= choices.max_choices:
                break
        return selections
