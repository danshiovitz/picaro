import random

from skills import SKILLS

class Character:
    def __init__(self, name, job):
        self.name = name
        self.job = job
        self.turns = 20
        self.health = 20
        self.coins = 0
        self.resources = 0
        self.reputation = 0
        self.max_reputation = 10
        self.luck = 5
        self.tools = []
        self.skills = {s: 0 for s in SKILLS}

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
