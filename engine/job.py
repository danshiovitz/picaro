import random
from typing import List, Tuple

from .deck import EncounterDeck
from .types import TemplateCard


class Job:
    def __init__(self, name: str, base_skills: List[str], base_difficulty: int, cards: List[TemplateCard], encounter_distances: List[int]):
        self.name = name
        self.base_skills = base_skills
        self.base_difficulty = base_difficulty
        self.cards = cards
        self.encounter_distances = encounter_distances

    def make_deck(self, additional: List[Tuple[TemplateCard, int]] = None) -> EncounterDeck:
        probs = [4, 2, 1, 1, 1, 1]
        while len(probs) < len(self.cards):
            probs.append(1)
        quantities = list(zip(self.cards, probs))
        if additional:
            quantities += additional
        return EncounterDeck(quantities, self.base_skills, self.base_difficulty)
