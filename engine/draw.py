#!/usr/bin/python3
import random
import sys
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum


def flatten(*card_counts):
   flat = []
   for card, count in card_counts:
     for _ in range(count):
       flat.append(card)
   return tuple(flat)


SKILLS = (
    "Dueling",
    "Formation Fighting",
    "Brutal Fighting",
    "Shoot",
    "Throw",
    "Ride",

    "Research",
    "Debate",
    "Charm",
    "Carousing",
    "Thaumaturgy",
    "Spirit Binding",

    "Mechanisms",
    "Endurance",
    "Stealth",
    "Animal Training",
    "Might",
    "Climb",

    "Desert Lore",
    "Forest Lore",
    "Sea Lore",
    "Mountain Lore",
    "Jungle Lore",
    "Plains Lore",

    "Command",
    "Observation",
    "Mesmerism",
    "Acrobatics",
    "Appraisal",
    "Speed",

    "Pickpocket",
    "Doctor",
    "Architecture",
    "Navigation",
    "Skill X",
    "Skill Y",
)

JOB_CARDS = flatten(
    ("Caravan Raid", 4),
    ("Scouting Mission", 4),
    ("Another Band", 2),
    ("Guard Patrol", 2),
    ("Hunting Expedition", 1),
    ("Victory Celebration", 1),
    ("Test of Skill", 1),
    ("Aftermath of Battle", 1)
)

HEX_CARDS = flatten(
    ("Oasis", 2),
    ("Sandstorm", 2),
    ("Valley", 2),
    ("Cliff", 2),
    ("Desert Beast", 2),
    ("Extreme Heat", 2),
    ("Strange Constellations", 2),
    ("Desert Mystic", 2)
)


class Difficulty(Enum):
 EASY = 0
 MEDIUM = 1
 HARD = 2
 VERY_HARD = 3

class Result(Enum):
    FAILURE = 0
    MIXED = 1
    SUCCESS = 2
    GREAT_SUCCESS = 3

class Card(ABC):
    def __init__(self, name):
        self.name_ = name

    @property
    def name(self):
        return self.name_

    @abstractmethod
    def play(self) -> str:
        pass

class ChallengeCard(Card):
    def __init__(self, name, difficulty, skill=None, zodiacs=None):
        super().__init__(name)
        self.difficulty = difficulty
        self.skill = skill or random.choice(SKILLS)
        self.zodiacs = zodiacs or random.sample(ZODIACS, 2)

    def play(self) -> str:
        print("{}: {} - {} {}".format(self.name, self.difficulty.name, self.skill, self.zodiacs))
        return ""

class DrawCard(Card):
    def __init__(self, deck_name):
        super().__init__("Draw " + deck_name)
        self.deck_name = deck_name

    def play(self) -> str:
        print("Draw instead from {}".format(self.deck_name))
        return ""

def gen_job_deck():
    cards = []

    jc = list(JOB_CARDS[:])
    random.shuffle(jc)
    while jc:
      cards.append(ChallengeCard(name=jc.pop(), difficulty=Difficulty.MEDIUM))

    hc = list(HEX_CARDS[:])
    random.shuffle(hc)
    for _ in range(4):
        cards.append(ChallengeCard(name=hc.pop(), difficulty=Difficulty.MEDIUM))

    for _ in range(4):
        cards.append(DrawCard(deck_name="project"))

    for _ in range(4):
        cards.append(DrawCard(deck_name="lifepath"))

    random.shuffle(cards)
    return cards[0:20]


def main():
    print("The season begins!")
    print("")
    deck = gen_job_deck()
    while deck:
        card = deck.pop(0)
        card.play()
        print("Commentary: ", end="")
        line = input()
        print()
    print("The season has ended.")

if __name__ == "__main__":
    main()
