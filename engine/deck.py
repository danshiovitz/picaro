import random
from dataclasses import dataclass
from string import ascii_lowercase
from typing import Generic, List, Sequence, Tuple, TypeVar

from .skills import load_skills
from .storage import ObjectStorageBase
from .types import ChoiceType, EncounterCheck, EffectType, FullCard, TemplateCard
from .zodiacs import load_zodiacs


@dataclass(frozen=True)
class EncounterDeck:
    name: str
    templates: Sequence[TemplateCard]
    base_skills: Sequence[str]

    def actualize(self, difficulty: int, additional: List[TemplateCard] = None) -> List[FullCard]:
        ret = []
        for tmpl in list(self.templates) + (additional or []):
            for _ in range(tmpl.copies):
                ret.append(self._make_card(tmpl, difficulty))
        random.shuffle(ret)
        for _ in range((len(ret) // 10) + 1):
            ret.pop()
        return ret

    def _make_card(self, val: TemplateCard, difficulty: int) -> FullCard:
        if not val.skills:
            checks = []
            choice_type = val.choice_type
            choices = val.choices
        else:
            choice_type = ChoiceType.NONE
            choices = []
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

        card_id = "".join(random.choice(ascii_lowercase) for _ in range(12))
        return FullCard(id=card_id, name=val.name, desc=val.desc, checks=checks, choice_type=choice_type, choices=choices, signs=signs)

    def _make_check(self, difficulty: int, skill_bag: List[str], reward_bag: List[EffectType], penalty_bag: List[EffectType]) -> EncounterCheck:
        tn = self.difficulty_to_target_number(difficulty)
        # fuzz the tns a bit
        fuzzed = [
            tn, tn, tn, tn,
            tn + 1, tn + 1, tn - 1, tn - 1,
            tn + 2, tn - 2, tn + 3, tn - 3,
        ]
        # was ending up with some TN 1 or TN 0, which seems pretty lame
        fuzzed = [tn for tn in fuzzed if tn >= 2]
        tn = random.choice(fuzzed)
        return EncounterCheck(skill=random.choice(skill_bag), target_number=tn, reward=random.choice(reward_bag), penalty=random.choice(penalty_bag))

    # originally had this as a deck, but I think it works better to have more hot/cold variance
    def _make_reward_bag(self, template_card: TemplateCard) -> List[EffectType]:
        reward_bag = []
        reward_bag.extend([EffectType.GAIN_COINS, EffectType.GAIN_REPUTATION] * 4)
        reward_bag.extend(template_card.rewards * 4)
        reward_bag.extend([EffectType.GAIN_RESOURCES, EffectType.GAIN_HEALING, EffectType.GAIN_QUEST, EffectType.NOTHING] * 1)
        return reward_bag

    def _make_penalty_bag(self, template_card: TemplateCard) -> List[EffectType]:
        penalty_bag = []
        penalty_bag.extend([EffectType.DAMAGE] * 12)
        penalty_bag.extend(template_card.penalties * 6)
        penalty_bag.extend([EffectType.NOTHING, EffectType.LOSE_REPUTATION, EffectType.LOSE_RESOURCES, EffectType.LOSE_COINS, EffectType.TRANSPORT, EffectType.DISRUPT_JOB] * 1)
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
