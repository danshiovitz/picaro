import curses
import curses.textpad
import re
from collections import defaultdict
from string import ascii_lowercase
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar

from picaro.server.api_types import *

from .common import IllegalMoveException
from .render import render_effect, render_feat


def read_text(prompt: str, textbox: bool = False) -> str:
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
# What feats does the emblem provide?
# > modify search skill +1
# > done

T = TypeVar("T")


class ComplexReader:
    def __init__(
        self,
        default_entity: Optional[Tuple[EntityType, str]],
        board: Board,
        skills: List[str],
        jobs: List[Job],
    ):
        self.default_entity = default_entity
        self.board = board
        self.skills = skills
        self.jobs = jobs

    def read_effects(
        self,
        prompt: str,
        init: List[Effect],
    ) -> List[Effect]:
        skills = self.skills
        resources = self.board.resources
        job_names = [j.name for j in self.jobs]
        hexes = [h.name for h in self.board.hexes]
        fixup = lambda v: (v[0], True, v[1])
        effect_choices = [
            (
                "Modify coins <amount>",
                lambda ln, e: self._lparse_effect(EffectType.MODIFY_COINS, e, ln),
            ),
            (
                "Modify xp <amount> <skill or 'free'>",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_XP, e, ln, subtypes=skills, none_type="free"
                ),
            ),
            (
                "Modify reputation <amount>",
                lambda ln, e: self._lparse_effect(EffectType.MODIFY_REPUTATION, e, ln),
            ),
            (
                "Modify health <amount>",
                lambda ln, e: self._lparse_effect(EffectType.MODIFY_HEALTH, e, ln),
            ),
            (
                "Modify resources <amount> <resource or 'draw'>",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_RESOURCES,
                    e,
                    ln,
                    subtypes=board.resources,
                    none_type="draw",
                ),
            ),
            (
                "Modify turns <amount>",
                lambda ln, e: self._lparse_effect(EffectType.MODIFY_TURNS, e, ln),
            ),
            (
                "Use up activity",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_ACTIVITY,
                    e,
                    ln,
                    lparse_val=lambda ln: (-1, True, ln),
                ),
            ),
            (
                "Refresh activity",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_ACTIVITY,
                    e,
                    ln,
                    lparse_val=lambda ln: (1, True, ln),
                ),
            ),
            (
                "Modify location",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_LOCATION,
                    e,
                    ln,
                    lparse_val=lambda ln: fixup(
                        self._lparse_fixedstr("hex", ln, hexes)
                    ),
                ),
            ),
            (
                "Modify job",
                lambda ln, e: self._lparse_effect(
                    EffectType.MODIFY_JOB,
                    e,
                    ln,
                    lparse_val=lambda ln: fixup(
                        self._lparse_fixedstr("job", ln, job_names)
                    ),
                ),
            ),
            (
                "Add emblem",
                lambda ln, e: self._lparse_effect(
                    EffectType.ADD_EMBLEM,
                    e,
                    ln,
                    lparse_val=lambda ln: fixup(self._lparse_emblem(ln)),
                ),
            ),
            (
                "Random transport",
                lambda ln, e: self._lparse_effect(EffectType.TRANSPORT, e, ln),
            ),
            (
                "Leadership challenge",
                lambda ln, e: self._lparse_effect(EffectType.LEADERSHIP, e, ln),
            ),
        ]

        return self._read_complex(
            prompt, init, self.default_entity, effect_choices, render_effect
        )

    def read_feats(
        self,
        prompt: str,
        init: List[Feat],
    ) -> List[Feat]:
        skills = self.skills
        feat_choices = [
            (
                "Modify init tableau age <amount>",
                lambda ln, e: self._lparse_feat(HookType.INIT_TABLEAU_AGE, e, ln),
            ),
            (
                "Modify init turns <amount>",
                lambda ln, e: self._lparse_feat(HookType.INIT_TURNS, e, ln),
            ),
            (
                "Modify max health <amount>",
                lambda ln, e: self._lparse_feat(HookType.MAX_HEALTH, e, ln),
            ),
            (
                "Modify max luck <amount>",
                lambda ln, e: self._lparse_feat(HookType.MAX_LUCK, e, ln),
            ),
            (
                "Modify max tableau size <amount>",
                lambda ln, e: self._lparse_feat(HookType.MAX_TABLEAU_SIZE, e, ln),
            ),
            (
                "Modify skill rank <amount> <skill>",
                lambda ln, e: self._lparse_feat(
                    HookType.SKILL_RANK, e, ln, subtypes=skills
                ),
            ),
            (
                "Modify skill reliability <amount> <skill>",
                lambda ln, e: self._lparse_feat(
                    HookType.RELIABLE_SKILL, e, ln, subtypes=skills
                ),
            ),
            (
                "Modify init speed <amount>",
                lambda ln, e: self._lparse_feat(HookType.INIT_SPEED, e, ln),
            ),
            (
                "Modify resource limit <amount>",
                lambda ln, e: self._lparse_feat(HookType.MAX_RESOURCES, e, ln),
            ),
        ]

        return self._read_complex(
            prompt, init, self.default_entity, feat_choices, render_feat
        )

    def _read_complex(
        self,
        prompt: str,
        init: List[T],
        default_entity: Optional[Tuple[EntityType, str]],
        choice_list: List[
            Tuple[str, Callable[[str, Optional[Tuple[EntityType, str]]], Tuple[T, str]]]
        ],
        render_func: Callable[[T], str],
    ) -> List[T]:
        print(prompt)
        items = init[:]
        cur_entity = default_entity
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
                item, line = choice_list[choice_idx][1](line, cur_entity)
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
        ent: Optional[Tuple[EntityType, str]],
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
                entity_type=ent[0] if ent else None,
                entity_name=ent[1] if ent else None,
            ),
            line,
        )

    def _lparse_emblem(
        self,
        line: str,
    ) -> Tuple[Emblem, str]:
        name, line = self._lparse_str("name", line)
        feats = self.read_feats("Enter feats for this emblem:", [])
        return Emblem(name, feats), line

    def _lparse_feat(
        self,
        hook_type: HookType,
        ent: Optional[Tuple[EntityType, str]],
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
            Feat(
                hook=hook_type,
                value=val,
                subtype=subtype,
            ),
            line,
        )


def read_selections(choices: Choices, rolls: Sequence[int]) -> Dict[int, int]:
    selections = defaultdict(int)
    can_choose = True
    if choices.is_random:
        for v in rolls:
            selections[v - 1] += 1
        can_choose = False
    elif choices.min_choices >= sum(c.max_choices for c in choices.choice_list):
        for idx, c in enumerate(choices.choice_list):
            selections[idx] = c.max_choices
        can_choose = False

    while True:
        if choices.benefit or choices.cost:
            line = " ** Overall: " + ", ".join(
                render_effect(eff) for eff in choices.benefit + choices.cost
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
                render_effect(eff) for eff in list(choice.benefit) + list(choice.cost)
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
