import random

from common import Result
from skills import SKILLS

class Character:
    def __init__(self, name, job):
        self.name = name
        self.job = job
        self.turns = 20
        self.danger = 0
        self.coins = 0
        self.resources = 0
        self.reputation = 0
        self.max_reputation = 10
        self.tools = []
        self.skills = {s: 0 for s in SKILLS}
        self.competence = 2

    def skill_check(self, skill, difficulty):
        CHANCES = {
            # the ratios of failure:mixed:success+great is just extrapolated
            # from hand-set values for -3, 0, +3; the fraction of the successes
            # which are great successes is 1/(5 - advantage)
            -3: (80, 10,  9, 1),
            -2: (60, 20, 17, 3),
            -1: (45, 30, 20, 5),
             0: (30, 40, 25, 5),
             1: (20, 40, 30, 10),
             2: (15, 35, 35, 15),
             3: (10, 30, 30, 30), 
        }

        sk = self.competence + self.skills[skill]
        advantage = max(min(sk - difficulty, 3), -3)
        roll = random.randint(1, 100)
        print("Rolled: {}".format(roll))
        if roll <= CHANCES[advantage][0]:
            return Result.FAILURE
        roll -= CHANCES[advantage][0]
        if roll <= CHANCES[advantage][1]:
            return Result.MIXED
        roll -= CHANCES[advantage][1]
        if roll <= CHANCES[advantage][2]:
            return Result.SUCCESS
        roll -= CHANCES[advantage][2]
        if roll <= CHANCES[advantage][3]:
            return Result.GREAT_SUCCESS
        raise Exception("The roll was bad! {} {}".format(roll, advantage))

    def advance(self, skill, xp):
        if skill in self.job.learn_skills:
            print("This is a core skill")
            xp *= 2
        if random.randint(1, 100) < xp * 10:
            self.skills[skill] += 1
            print("Skill {} is now {}".format(skill, self.skills[skill]))
        else:
            print("Skill {} improves".format(skill))

    def end_turn(self):
        self.turns -= 1
        if self.reputation >= self.max_reputation:
            print("Promotion!")
            self.reputation = 0
            self.max_reputation += 5
            self.danger = 0
        else:
            self.reputation = max(0, self.reputation - 1)
        print("Commentary: ", end="")
        line = input()
        print()

    def check_danger(self):
        if random.randint(1, 10) <= self.danger:
            print("Dangerous slip! You fall!")
            self.danger = 0
            self.max_reputation = max(5, self.max_reputation - 5)
            self.reputation = 0
        else:
            print("A brush with danger ...")

if __name__ == "__main__":
    ch = Character("Tester")
    sk = next(iter(SKILLS))
    ch.skills[sk] = 4

    for d in range(0, 9):
        cnts = [0, 0, 0, 0]
        rounds = 10000
        for _ in range(0, rounds):
            cnts[ch.skill_check(sk, d).value] += 1
        print("Difficulty: {} - {}".format(d, [int(c * 100 / rounds) for c in cnts]))
            
        
