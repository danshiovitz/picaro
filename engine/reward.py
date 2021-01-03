import random
from enum import Enum

from common import Deck, flatten
from skills import SKILLS


class Result(Enum):
    FAILURE = 0
    MIXED = 1
    SUCCESS = 2
    GREAT_SUCCESS = 3


class Reward(Enum):
     COINS = 1,
     RESOURCES = 2,
     XP_BASE = 3,
     XP_RANDOM = 4,
     REPUTATION = 5,
     TOOL = 6

rewards = Deck(flatten(
            (Reward.COINS, 2),
            (Reward.RESOURCES, 1),
            (Reward.XP_BASE, 2),
            (Reward.XP_RANDOM, 1),
            (Reward.REPUTATION, 4),
            (Reward.TOOL, 1),
          ))


def add_reward_penalty(rank, result, base_skill, pc):
    if result != Result.FAILURE:
        add_reward(rank, base_skill, pc)
    if result == Result.GREAT_SUCCESS:
        pc.reputation += 1
        pc.danger = max(0, pc.danger - 1)
    elif result == Result.SUCCESS:
        pc.reputation += 1
        pass
    elif result == Result.MIXED:
        pc.reputation += 1
        pc.danger += 1
    elif result == Result.FAILURE:
        pc.advance(base_skill, 2)
        pc.danger += 2
        pc.check_danger()
    else:
        raise Exception("Result? {}".format(result))


def add_reward (rank, base_skill, pc):
    card = rewards.draw()
    if card == Reward.COINS:
        print("Cha-ching")
        pc.coins += (rank * 4)
    elif card == Reward.RESOURCES:
        print("Cha-resource")
        pc.resources += rank
        pc.coins += (rank * 2)
    elif card == Reward.XP_BASE:
        pc.advance(base_skill, 3)
    elif card == Reward.XP_RANDOM:
        sk = random.choice(list(SKILLS))
        pc.advance(sk, 5)
    elif card == Reward.REPUTATION:
        print("Lookin' good")
        pc.reputation += rank + 1
    elif card == Reward.TOOL:
        print("Useful rock")
        pc.tools += "a tool"
    else:
        raise Exception("Which card? {}".format(card))
