import random
from typing import Generic, List, NamedTuple, Tuple, TypeVar

from .skills import load_skills
from .storage import ObjectStorageBase
from .types import EncounterCheck, EncounterPenalty, EncounterReward, FullCard, TemplateCard
from .zodiacs import load_zodiacs


NEXT_ID = 1

class EncounterDeck(NamedTuple):
    name: str
    templates: List[TemplateCard]
    base_skills: List[str]

    def actualize(self, difficulty: int, additional: List[TemplateCard] = None) -> List[FullCard]:
        ret = []
        for tmpl in self.templates + (additional or []):
            for _ in range(tmpl.copies):
                ret.append(self._make_card(tmpl, difficulty))
        random.shuffle(ret)
        for _ in range((len(ret) // 10) + 1):
            ret.pop()
        return ret

    def _make_card(self, val: TemplateCard, difficulty: int) -> FullCard:
        if not val.skills:
            checks = []
        else:
            skill_bag = []
            skill_bag.extend(self.base_skills * 15)
            skill_bag.extend(val.skills * 15)

            all_skills = load_skills()
            reward_bag = self._make_reward_bag(val)
            penalty_bag = self._make_penalty_bag(val)
            checks = [
                self._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                self._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                self._make_check(difficulty, skill_bag + all_skills, reward_bag, penalty_bag),
            ]

        all_zodiacs = load_zodiacs()
        signs = random.sample(all_zodiacs, 2)

        global NEXT_ID
        card_id = NEXT_ID
        NEXT_ID += 1
        return FullCard(id=card_id, template=val, checks=checks, signs=signs)

    def _make_check(self, difficulty: int, skill_bag: List[str], reward_bag: List[EncounterReward], penalty_bag: List[EncounterPenalty]) -> EncounterCheck:
        tn = self.difficulty_to_target_number(difficulty)
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


def load_deck(deck_name: str) -> EncounterDeck:
    return DeckStorage.load_by_name(deck_name)


class TemplateCardStorage(ObjectStorageBase[TemplateCard]):
    TABLE_NAME = "template_card"
    TYPE = TemplateCard
    PRIMARY_KEY = "name"

    @classmethod
    def load(cls) -> List[TemplateCard]:
        return cls._select_helper([], {}, active_conn=None)

    @classmethod
    def load_by_name(cls, name) -> TemplateCard:
        cards = cls._select_helper(["name = :name"], {"name": name}, active_conn=None)
        if not cards:
            raise Exception(f"No such card: {name}")
        return cards[0]


class DeckStorage(ObjectStorageBase[EncounterDeck]):
    TABLE_NAME = "template_deck"
    TYPE = EncounterDeck
    PRIMARY_KEY = "name"
    SUBCLASSES = {"template_cards": TemplateCardStorage}

    @classmethod
    def load(cls) -> List[EncounterDeck]:
        return cls._select_helper([], {}, active_conn=None)

    @classmethod
    def load_by_name(cls, name) -> EncounterDeck:
        decks = cls._select_helper(["name = :name"], {"name": name}, active_conn=None)
        if not decks:
            raise Exception(f"No such deck: {name}")
        return decks[0]
