import random
from typing import Generic, List, Tuple, TypeVar

from .skills import SKILLS
from .types import EncounterCheck, EncounterPenalty, EncounterReward, FullCard, TemplateCard
from .zodiacs import ZODIACS


S = TypeVar("S")
T = TypeVar("T")

class Deck(Generic[S, T]):
    def __init__(self, deck_template: List[Tuple[S, int]]) -> None:
        self.deck_template = deck_template
        self.cards: List[T] = []

    def draw(self) -> T:
        if not self.cards:
            self._refill_cards()
        return self.cards.pop(0)

    def _refill_cards(self) -> None:
        self.cards = []
        for val, cnt in self.deck_template:
            for _ in range(cnt):
                self.cards.append(self._make_card(val))
        random.shuffle(self.cards)
        for _ in range(3):
            self.cards.pop()

    def _make_card(self, val: S) -> T:
        return val


class EncounterDeck(Deck[TemplateCard, FullCard]):
    NEXT_ID = 1

    def __init__(self, deck_template: List[Tuple[TemplateCard, int]], base_skills: List[str], base_difficulty: int) -> None:
        super().__init__(deck_template)
        self.base_skills = base_skills
        self.base_difficulty = base_difficulty

    def _make_card(self, val: TemplateCard) -> FullCard:
        if not val.skills:
            checks = []
        else:
            skill_bag = []
            skill_bag.extend(self.base_skills * 15)
            skill_bag.extend(val.skills * 15)

            reward_bag = self._make_reward_bag(val)
            penalty_bag = self._make_penalty_bag(val)
            checks = [
                self._make_check(skill_bag, reward_bag, penalty_bag),
                self._make_check(skill_bag, reward_bag, penalty_bag),
                self._make_check(skill_bag + list(SKILLS), reward_bag, penalty_bag),
            ]

        signs = random.sample(ZODIACS, 2)

        card_id = self.NEXT_ID
        self.NEXT_ID += 1
        return FullCard(id=card_id, template=val, checks=checks, signs=signs)

    def _make_check(self, skill_bag: List[str], reward_bag: List[EncounterReward], penalty_bag: List[EncounterPenalty]) -> EncounterCheck:
        tn = self.difficulty_to_target_number(self.base_difficulty)
        # fuzz the tns a bit
        tn = random.choice([
            tn, tn, tn, tn,
            tn + 1, tn + 1, tn - 1, tn - 1,
            tn + 2, tn - 2, tn + 3, tn - 3,
        ])
        return EncounterCheck(skill=random.choice(skill_bag), target_number=tn, reward=random.choice(reward_bag), penalty=random.choice(penalty_bag))

    # originally had this as a deck, but I think it works better to have more hot/cold variance
    def _make_reward_bag(self, template_card: TemplateCard) -> List[EncounterReward]:
        reward_bag = []
        reward_bag.extend([EncounterReward.COINS, EncounterReward.REPUTATION] * 4)
        reward_bag.extend(template_card.rewards * 4)
        reward_bag.extend([EncounterReward.RESOURCES, EncounterReward.HEALING, EncounterReward.QUEST, EncounterReward.NOTHING] * 1)
        return reward_bag

    def _make_penalty_bag(self, template_card: TemplateCard) -> List[EncounterPenalty]:
        penalty_bag = []
        penalty_bag.extend([EncounterPenalty.DAMAGE] * 12)
        penalty_bag.extend(template_card.penalties * 6)
        penalty_bag.extend([EncounterPenalty.NOTHING, EncounterPenalty.REPUTATION, EncounterPenalty.RESOURCES, EncounterPenalty.COINS, EncounterPenalty.TRANSPORT, EncounterPenalty.JOB] * 1)
        return penalty_bag

    def difficulty_to_target_number(self, difficulty: int) -> int:
        return difficulty * 2 + 1
