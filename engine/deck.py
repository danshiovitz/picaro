import random
from dataclasses import dataclass
from string import ascii_lowercase
from typing import Generic, List, Sequence, Tuple, TypeVar

from .exceptions import IllegalMoveException
from .skills import load_skills
from .storage import ObjectStorageBase
from .types import (
    Choices,
    EncounterCheck,
    EncounterContextType,
    EncounterEffect,
    FullCard,
    TemplateCard,
)
from .zodiacs import load_zodiacs


@dataclass(frozen=True)
class TemplateDeck:
    name: str
    templates: Sequence[TemplateCard]
    base_skills: Sequence[str]

    def actualize(
        self,
        difficulty: int,
        context: EncounterContextType,
        additional: List[TemplateCard] = None,
    ) -> List[FullCard]:
        ret = []
        for tmpl in self.semi_actualize(additional):
            ret.append(self.make_card(tmpl, difficulty, context))
        return ret

    def semi_actualize(
        self, additional: List[TemplateCard] = None
    ) -> List[TemplateCard]:
        ret = []
        for tmpl in list(self.templates) + (additional or []):
            for _ in range(tmpl.copies):
                ret.append(tmpl)
        random.shuffle(ret)
        for _ in range((len(ret) // 10) + 1):
            ret.pop()
        return ret

    def make_card(
        self, val: TemplateCard, difficulty: int, context: EncounterContextType
    ) -> FullCard:
        if not val.skills:
            checks = []
            choices = val.choices
        else:
            choices = None
            skill_bag = []
            # the number of copies of the core skills only matters on the third check,
            # where we add in all the skills (let's assume there are 36) and want to
            # have the copy number such that we pick a core skill (let's assume there
            # are 6) say 50% of the time and an unusual skill 50% of the time
            skill_bag.extend(self.base_skills * 6)
            skill_bag.extend(val.skills * 6)

            all_skills = load_skills()
            reward_bag = self._make_reward_bag(val, context)
            penalty_bag = self._make_penalty_bag(val, context)
            checks = [
                self._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                self._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                self._make_check(
                    difficulty, skill_bag + all_skills, reward_bag, penalty_bag
                ),
            ]

        all_zodiacs = load_zodiacs()
        signs = random.sample(all_zodiacs, 2) if not val.unsigned else []

        card_id = "".join(random.choice(ascii_lowercase) for _ in range(12))
        return FullCard(
            id=card_id,
            name=val.name,
            desc=val.desc,
            checks=checks,
            choices=choices,
            signs=signs,
        )

    def _make_check(
        self,
        difficulty: int,
        skill_bag: List[str],
        reward_bag: List[EncounterEffect],
        penalty_bag: List[EncounterEffect],
    ) -> EncounterCheck:
        tn = self.difficulty_to_target_number(difficulty)
        # fuzz the tns a bit
        fuzzed = [
            tn,
            tn,
            tn,
            tn,
            tn + 1,
            tn + 1,
            tn - 1,
            tn - 1,
            tn + 2,
            tn - 2,
            tn + 3,
            tn - 3,
        ]
        # was ending up with some TN 1 or TN 0, which seems pretty lame
        fuzzed = [tn for tn in fuzzed if tn >= 2]
        tn = random.choice(fuzzed)
        return EncounterCheck(
            skill=random.choice(skill_bag),
            target_number=tn,
            reward=random.choice(reward_bag),
            penalty=random.choice(penalty_bag),
        )

    # originally had this as a deck, but I think it works better to have more hot/cold variance
    def _make_reward_bag(
        self, template_card: TemplateCard, context: EncounterContextType
    ) -> List[EncounterEffect]:
        reward_bag = []
        reward_bag.extend(
            [EncounterEffect.GAIN_COINS, EncounterEffect.GAIN_REPUTATION] * 4
        )
        reward_bag.extend(template_card.rewards * 4)
        reward_bag.extend(
            [
                EncounterEffect.GAIN_RESOURCES,
                EncounterEffect.GAIN_HEALING,
                EncounterEffect.GAIN_QUEST,
                EncounterEffect.NOTHING,
            ]
            * 1
        )
        return reward_bag

    def _make_penalty_bag(
        self, template_card: TemplateCard, context: EncounterContextType
    ) -> List[EncounterEffect]:
        penalty_bag = []
        if context == EncounterContextType.TRAVEL:
            penalty_bag.extend([EncounterEffect.LOSE_SPEED] * 8)
            penalty_bag.extend([EncounterEffect.DAMAGE] * 4)
        else:
            penalty_bag.extend([EncounterEffect.DAMAGE] * 12)
        penalty_bag.extend(template_card.penalties * 6)
        penalty_bag.extend(
            [
                EncounterEffect.NOTHING,
                EncounterEffect.LOSE_REPUTATION,
                EncounterEffect.LOSE_RESOURCES,
                EncounterEffect.LOSE_COINS,
                EncounterEffect.TRANSPORT,
                EncounterEffect.DISRUPT_JOB,
            ]
            * 1
        )
        return penalty_bag

    def difficulty_to_target_number(self, difficulty: int) -> int:
        return difficulty * 2 + 1


def load_deck(deck_name: str) -> TemplateDeck:
    return TemplateDeckStorage.load_by_name(deck_name)


class TemplateCardStorage(ObjectStorageBase[TemplateCard]):
    TABLE_NAME = "template_card"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[TemplateCard]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name) -> TemplateCard:
        cards = cls._select_helper(["name = :name"], {"name": name})
        if not cards:
            raise IllegalMoveException(f"No such card: {name}")
        return cards[0]


class TemplateDeckStorage(ObjectStorageBase[TemplateDeck]):
    TABLE_NAME = "template_deck"
    PRIMARY_KEYS = {"name"}
    SUBCLASSES = {"template_cards": TemplateCardStorage}

    @classmethod
    def load(cls) -> List[TemplateDeck]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name) -> TemplateDeck:
        decks = cls._select_helper(["name = :name"], {"name": name})
        if not decks:
            raise IllegalMoveException(f"No such deck: {name}")
        return decks[0]
