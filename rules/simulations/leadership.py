import random
import sys
from collections import defaultdict
from enum import Enum, auto as enum_auto
from pathlib import Path

sys.path.append(str(Path(__file__).absolute().parent.parent.parent.parent))

from typing import List


class Result(Enum):
    CRIT_FAILURE = enum_auto()
    FAILURE = enum_auto()
    SUCCESS = enum_auto()
    CRIT_SUCCESS = enum_auto()


def existing_one(reputation: int, difficulty_mod: int) -> Result:
    target_number = 5 - difficulty_mod
    bonus = reputation
    roll = random.randint(1, 8)
    if roll + bonus < target_number:
        if roll == 1:
            return Result.CRIT_FAILURE
        else:
            return Result.FAILURE
    elif roll + bonus < target_number + 4:
        return Result.SUCCESS
    else:
        return Result.CRIT_SUCCESS


def checks_one(reputation: int, difficulty_mod: int) -> Result:
    target_number = 4 - difficulty_mod
    if reputation == 0:
        target_number += 1
        reputation += 1
    successes = 0
    for _ in range(0, reputation + 1):
        roll = random.randint(1, 8)
        if roll >= target_number:
            successes += 1
    if successes == 0:
        return Result.CRIT_FAILURE
    elif successes == 1:
        return Result.FAILURE
    elif successes == 2:
        return Result.SUCCESS
    else:
        return Result.CRIT_SUCCESS


def run() -> None:
    turns = 10000

    reputation = 1
    difficulty_mod = -1

    for reputation in range(0, 6):
        results = defaultdict(int)
        for _ in range(turns):
            result = checks_one(reputation, difficulty_mod)
            results[result] += 1

        pcts = {k: results[k] / turns * 100 for k in list(Result)}
        print(
            f"@{reputation}: "
            + "; ".join(f"{k.name}: {pcts[k]:.1f}%" for k in list(Result))
        )


if __name__ == "__main__":
    run()
