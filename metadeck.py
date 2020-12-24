#!/usr/bin/python3
import random
from collections import defaultdict
from enum import Enum

from common import Deck, flatten
from reward import add_reward_penalty
from skills import SKILLS
from zodiacs import ZODIACS


class FullCard:
    def __init__(self, name, base_skill, difficulty, zodiacs):
        self.name = name
        self.base_skill = base_skill
        self.difficulty = difficulty
        self.zodiacs = zodiacs

    def display(self, pc):
        print("{} [signs: {}]".format(
            self.name,
            ", ".join(self.zodiacs)))
        print("Base skill: {} [skill: Rank {}, difficulty: Rank {}]".format(self.base_skill, pc.skills[self.base_skill], self.difficulty))

    def resolve(self, pc, hexmap):
        while True:
            print("Roll, extra danger, flee: ", end="")
            line = input().lower()
            if not line:
                continue
            if line[0] == "f":
                print("You flee!")
                pc.turns -= 1
                return
            elif line[0] == "r" or line[0] in ("e", "x", "d"):
                diff = self.difficulty
                if line[0] in ("e", "x", "d"):
                    diff -= 1
                    pc.danger += 1
                msgs = ["A failure :C", "A partial success :/", "A success :)", "A major success! :D"]
                result = pc.skill_check(self.base_skill, diff)
                print(msgs[result.value])
                add_reward_penalty(self.difficulty, result, self.base_skill, pc)
                return
            else:
                print("???")
                print()
            
class Metacard(Enum):
    JOB = 1
    HEX = 2

        
class MetaDeck:
    def __init__(self):
        self._meta_cards = Deck(flatten(
            (Metacard.JOB, 8),
            (Metacard.HEX, 4),
        ))
        self._difficulties = defaultdict(list)

    def draw_job(self, pc, cur_hex):
        mc = self._meta_cards.draw()
        return self.draw_mc(pc, cur_hex, mc)

    def draw_hex(self, pc, cur_hex):
        mc = Metacard.HEX
        return self.draw_mc(pc, cur_hex, mc)
            
    def draw_mc(self, pc, cur_hex, mc):
        skill_bag = []
        if mc == Metacard.JOB:
            card = pc.job.draw()
            base_difficulty = pc.job.card_difficulty
            skill_bag.extend(list(pc.job.card_skills) * 15)
        else:
            card = cur_hex.draw()
            base_difficulty = cur_hex.card_difficulty
            skill_bag.extend(list(cur_hex.card_skills) * 15)
        skill_bag.extend(list(card.skills) * 15)
        # less random
        # skill_bag.extend(list(SKILLS))
        base_skill = random.choice(skill_bag)
        zodiacs = random.sample(ZODIACS, 2)
        difficulty = self._get_difficulty(base_difficulty)
        return FullCard(name=card.name, base_skill=base_skill, difficulty=difficulty, zodiacs=zodiacs)
        
    def _shuffle(self, base_cards):
        cp = list(base_cards[:])
        random.shuffle(cp)
        for _ in range(2):
            cp.pop()
        return cp

    def _get_difficulty(self, base_difficulty):
        # less random
        return base_difficulty
    
        diffs = self._difficulties[base_difficulty]
        if not diffs:
            diffs.extend([base_difficulty] * 16)
            if base_difficulty > 1:
                diffs.extend([base_difficulty - 1] * 3)
            if base_difficulty > 2:
                diffs.extend([base_difficulty - 2] * 1)
            diffs.extend([base_difficulty + 1] * 3)
            diffs.extend([base_difficulty + 2] * 1)
            random.shuffle(diffs)
        return diffs.pop(0)
