#!/usr/local/bin/python3
import re
from dataclasses import dataclass
from random import randint
from typing import List, Tuple


@dataclass
class Stats:
    health: int
    gold: int
    luck: int


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


def roll(*, bonus: int = 0) -> int:
    return randint(1, 6) + bonus


def run_turn(stats: Stats, bonuses: List[int]) -> None:
    def _status(val):
        return "FAIL" if val < 6 else "SUCCESS"

    results = [roll(bonus=bonus) for bonus in bonuses]

    while True:
        for idx, res in enumerate(results):
            print(f"Check {idx+1}: {res} - {_status(res)}")
        cmd, args = choose(["flee", "f", 0], ["go", "g", 0], ["transfer", "t", 2], ["adjust", "a", 1])

        if cmd == "f":
            print("Fleeing!")
            return
        elif cmd == "g":
            statuses = [_status(res) for res in results]
            damage = len([1 for s in statuses if s == "FAIL"])
            gold = len([1 for s in statuses if s == "SUCCESS"])
            if gold > 0:
                gold = gold * 2 - 1
            print(f"You gain {gold} gold and take {damage} damage")
            stats.gold += gold
            stats.health -= damage
            return
        elif cmd == "t":
            from_c = int(args[0])
            to_c = int(args[1])
            if not (1 <= from_c <= 3):
                print(f"Bad val: {from_c}")
            elif not (1 <= to_c <= 3):
                print(f"Bad val: {to_c}")
            elif results[from_c - 1] < 2:
                print(f"Check {from_c} isn't high enough")
            else:
                results[from_c - 1] -= 2
                results[to_c - 1] += 1
        elif cmd == "a":
            to_c = int(args[0])
            if not (1 <= to_c <= 3):
                print(f"Bad val: {to_c}")
            elif stats.luck < 1:
                print(f"Luck isn't high enough")
            else:
                results[to_c - 1] += 1
                stats.luck -= 1
        else:
            print("???")

def run_game() -> None:
    stats = Stats(health=20, gold=0, luck=5)
    for t in range(1, 21):
        print(f"Turn {t}:")
        print(stats)
        run_turn(stats, [2, 1, 0])
        print()
        if stats.health <= 0:
            print("You perish! :C")
            return
        elif stats.gold >= 40:
            print("You are triumphant! :D")
            return
    print("You lose on time :C")

if __name__ == "__main__":
    run_game()
