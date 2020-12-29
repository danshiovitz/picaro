#!/usr/bin/python3
import random
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from random import randint

from common import Deck, choose, flatten
from reward import add_reward_penalty
from skills import SKILLS
from zodiacs import ZODIACS


@dataclass
class CardCheck:
    skill: str
    target_number: int

class FullCard:
    def __init__(self, name, target_hex, checks, zodiacs):
        self.name = name
        self.target_hex = target_hex
        self.checks = checks
        self.zodiacs = zodiacs
        self.duration = 3

    def preview(self, pc):
        sk = self.checks[0].skill
        diff = self.checks[0].target_number
        bonus = pc.skills[self.checks[0].skill]
        return (f"({self.duration}) {self.name}: " +
                f"{sk} (1d8{bonus:+}) vs {diff}" +
                (f" [{self.target_hex}]" if self.target_hex else "")
            )

    def resolve(self, pc, hexmap):
        print("{} [signs: {}]".format(
            self.name,
            ", ".join(self.zodiacs)))
        print("Some longer description about the card stuff")

        def _make_check(check, pc):
            bonus = pc.skills[check.skill]
            return randint(1, 8) + bonus

        def _eval_check(check, roll):
            return roll >= check.target_number

        if self.target_hex:
            hexmap.move_feature(pc.name, self.target_hex)

        rolls = [_make_check(check, pc) for check in self.checks]

        while True:
            print()
            for idx, check in enumerate(self.checks):
                sk = check.skill
                diff = check.target_number
                bonus = pc.skills[check.skill]
                roll = rolls[idx]
                status = "SUCCESS" if _eval_check(check, roll) else "FAILURE"
                print(f"Check #{idx+1}: {sk} (1d8{bonus:+}) vs {diff}: {roll} - {status}")
            cmd, args = choose(["flee", "f", 0], ["go", "g", 0], ["transfer", "t", 2], ["adjust", "a", 1])

            if cmd == "f":
                print("You flee!")
                return
            elif cmd == "g":
                evals = [_eval_check(self.checks[idx], roll) for (idx, roll) in enumerate(rolls)]
                damage = len([1 for s in evals if not s])
                coins = len([1 for s in evals if s])
                if coins > 0:
                    coins = coins * 2 - 1
                print(f"You gain {coins} coins and take {damage} damage")
                pc.coins += coins
                pc.health -= damage
                return
            elif cmd == "t":
                from_c = int(args[0])
                to_c = int(args[1])
                if not (1 <= from_c <= 3):
                    print(f"Bad val: {from_c}")
                elif not (1 <= to_c <= 3):
                    print(f"Bad val: {to_c}")
                elif rolls[from_c - 1] < 2:
                    print(f"Check {from_c} isn't high enough")
                else:
                    rolls[from_c - 1] -= 2
                    rolls[to_c - 1] += 1
            elif cmd == "a":
                to_c = int(args[0])
                if not (1 <= to_c <= 3):
                    print(f"Bad val: {to_c}")
                elif pc.luck < 1:
                    print(f"Luck isn't high enough")
                else:
                    rolls[to_c - 1] += 1
                    pc.luck -= 1
            else:
                print("???")


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

    def draw_job(self, pc, hexmap):
        mc = self._meta_cards.draw()
        return self.draw_mc(pc, hexmap, mc)

    def draw_hex(self, pc, hexmap):
        mc = Metacard.HEX
        return self.draw_mc(pc, hexmap, mc)

    def draw_mc(self, pc, hexmap, mc):
        skill_bag = []
        target_hex = None
        cur_hex = hexmap.find_feature(pc.name)
        distance = pc.job.get_move_distance()
        if distance > 0:
            target_hex = hexmap.random_path(pc.name, distance)
        else:
            target_hex = cur_hex
        if mc == Metacard.JOB:
            card = pc.job.draw()
            base_difficulty = pc.job.card_difficulty
            skill_bag.extend(list(pc.job.card_skills) * 15)
        else:
            card = target_hex.draw()
            base_difficulty = target_hex.card_difficulty
            skill_bag.extend(list(target_hex.card_skills) * 15)
        skill_bag.extend(list(card.skills) * 15)

        skills = [
            random.choice(skill_bag),
            random.choice(skill_bag),
        ]
        skill_bag.extend(list(SKILLS))
        skills.append(random.choice(skill_bag))
        random.shuffle(skills)
        # sort of dumb two-layer difficulty calculation: take the base rank,
        # then do a bell curve around it (which also converts the rank to a
        # target number), then do a smaller bell curve around that (which
        # adjusts the target number)
        curved_base = self._get_target_number(base_difficulty)
        diff_mods = [0, 0, 0, +1, -1]
        diffs = [curved_base + dm for dm in diff_mods]
        random.shuffle(diffs)
        checks = [CardCheck(skill=skill, target_number=diffs.pop(0)) for skill in skills]
        zodiacs = random.sample(ZODIACS, 2)
        return FullCard(name=card.name, target_hex=target_hex.name, checks=checks, zodiacs=zodiacs)

    def _shuffle(self, base_cards):
        cp = list(base_cards[:])
        random.shuffle(cp)
        for _ in range(2):
            cp.pop()
        return cp

    def _get_target_number(self, base_difficulty):
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
        d = diffs.pop(0)
        return d * 2 + 1
