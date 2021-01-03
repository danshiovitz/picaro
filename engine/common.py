import random
import re
from enum import Enum
from typing import List, Tuple

from colors import colors


def conj_list(items: List[str], conj: str) -> str:
    if len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f" {conj} ".join(items)
    else:
        return ", ".join(items[:-1]) + f", {conj} " + items[-1]


def choose(*options: List[Tuple[str, str, int]]) -> str:
    while True:
        print("You can " + conj_list([opt[0] for opt in options], "or") + ": ", end="")
        line = input().strip()
        input_cmd, *input_args = re.split(r'\s+', line)
        for cmd_name, cmd_val, cmd_argc in options:
            if cmd_val == input_cmd:
                if len(input_args) != cmd_argc:
                    print(f"Expected {cmd_argc} args")
                else:
                    return (cmd_val, input_args)

        print(f"Unknown input {line}")


def flatten(*thing_counts):
   flat = []
   for thing, count in thing_counts:
       flat.extend([thing] * count)
   return tuple(flat)

class Card:
    def __init__(self, name, skills):
        self.name = name
        self.skills = skills

class Deck:
    def __init__(self, cards):
        self._all_cards = cards
        self._current = []

    def draw(self):
        if not self._current:
            cp = list(self._all_cards[:])
            random.shuffle(cp)
            for _ in range(2):
                cp.pop()
            self._current = cp
        return self._current.pop(0)
