import random

from common import Card, Deck, flatten
from skills import *

class Job:
    def __init__(self):
        self.name = "Raider"
        self.learn_skills = { RIDE, BRUTAL_FIGHTING, ENDURANCE, DESERT_LORE, STEALTH, SHOOT }
        self.card_skills = { RIDE, ENDURANCE, STEALTH }
        self._move_distances = [0, 1, 1, 1, 2, 3]
        self.card_difficulty = 2
        self.cards = Deck(flatten(
            (Card("Caravan Raid", {SHOOT, SPEED, COMMAND}), 3),
            (Card("Scouting Mission", {OBSERVATION, CLIMB, APPRAISAL}), 2),
            (Card("Another Band", {MIGHT, CAROUSING, DEBATE}), 2),
            (Card("Guard Patrol", {STEALTH, FORMATION_FIGHTING, SPEED}), 2),
            (Card("Hunting Expedition", {SPEED, SHOOT, OBSERVATION}), 1),
            (Card("Victory Celebration", {CAROUSING, CHARM, ACROBATICS}), 1),
            (Card("Test of Skill", {SHOOT, ANIMAL_TRAINING, RIDE}), 1),
        ))

    def get_move_distance(self):
        return random.choice(self._move_distances)

    def draw(self):
        return self.cards.draw()
