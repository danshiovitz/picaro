import random
from enum import Enum

from colors import colors

class Result(Enum):
    FAILURE = 0
    MIXED = 1
    SUCCESS = 2
    GREAT_SUCCESS = 3

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
        

    
