import random
from typing import List, Sequence, TypeVar, cast

from picaro.common.storage import make_uuid

from .types.common import (
    Challenge,
    EncounterCheck,
    EncounterContextType,
    FullCard,
    FullCardType,
    Outcome,
    TemplateCard,
    TemplateCardType,
)
from .types.store import Game, TemplateDeck


T = TypeVar("T")


class DeckRules:
    @classmethod
    def shuffle(cls, cards: Sequence[T]) -> List[T]:
        ret = list(cards)
        random.shuffle(ret)
        for _ in range((len(ret) // 10) + 1):
            ret.pop()
        return ret

    @classmethod
    def load_deck(cls, name: str) -> List[TemplateCard]:
        template_deck = TemplateDeck.load(name)
        return cls.shuffle(c for c in template_deck.cards for _ in range(c.copies))

    @classmethod
    def make_card(
        cls,
        val: TemplateCard,
        base_skills: Sequence[str],
        difficulty: int,
        context_type: EncounterContextType,
    ) -> FullCard:
        game = Game.load()
        base_skills = list(base_skills)

        if val.type == TemplateCardType.CHOICE:
            data = val.data
            card_type = FullCardType.CHOICE
        elif val.type == TemplateCardType.CHALLENGE:
            challenge = cast(Challenge, val.data)
            skill_bag = []
            # the number of copies of the core skills only matters on the third check,
            # where we add in all the skills (let's assume there are 36) and want to
            # have the copy number such that we pick a core skill (let's assume there
            # are 6) say 50% of the time and an unusual skill 50% of the time
            sk = (list(challenge.skills) + base_skills + base_skills)[0:6]
            skill_bag.extend(sk * 6)

            reward_bag = cls._make_reward_bag(challenge, context_type)
            penalty_bag = cls._make_penalty_bag(challenge, context_type)
            if challenge.difficulty is not None:
                difficulty = challenge.difficulty
            data = [
                cls._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                cls._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
                cls._make_check(
                    difficulty,
                    skill_bag + list(game.skills),
                    reward_bag,
                    penalty_bag,
                ),
            ]
            card_type = FullCardType.CHALLENGE
        elif val.type == TemplateCardType.SPECIAL:
            data = val.data
            card_type = FullCardType.SPECIAL
        else:
            raise Exception(f"Unknown card type {val.type.name}")

        signs = random.sample(game.zodiacs, 2) if not val.unsigned else []

        return FullCard(
            uuid=make_uuid(),
            name=val.name,
            desc=val.desc,
            type=card_type,
            data=data,
            signs=signs,
            context_type=context_type,
            entity_type=val.entity_type,
            entity_name=val.entity_name,
        )

    @classmethod
    def _make_check(
        cls,
        difficulty: int,
        skill_bag: List[str],
        reward_bag: List[Outcome],
        penalty_bag: List[Outcome],
    ) -> EncounterCheck:
        tn = cls._difficulty_to_target_number(difficulty)
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

    # originally had this as a deck, but I think it works better to have more
    # hot/cold variance
    @classmethod
    def _make_reward_bag(
        cls, challenge: Challenge, context: EncounterContextType
    ) -> List[Outcome]:
        reward_bag = []
        reward_bag.extend([Outcome.GAIN_COINS, Outcome.GAIN_REPUTATION] * 4)
        reward_bag.extend(challenge.rewards * 4)
        reward_bag.extend(
            [
                Outcome.GAIN_RESOURCES,
                Outcome.GAIN_HEALING,
                Outcome.GAIN_PROJECT_XP,
                Outcome.GAIN_SPEED,
                Outcome.NOTHING,
            ]
            * 1
        )
        return reward_bag

    @classmethod
    def _make_penalty_bag(
        cls, challenge: Challenge, context: EncounterContextType
    ) -> List[Outcome]:
        penalty_bag = []
        if context == EncounterContextType.TRAVEL:
            penalty_bag.extend([Outcome.LOSE_SPEED] * 8)
            penalty_bag.extend([Outcome.DAMAGE] * 4)
        else:
            penalty_bag.extend([Outcome.DAMAGE] * 12)
        penalty_bag.extend(challenge.penalties * 6)
        penalty_bag.extend(
            [
                Outcome.NOTHING,
                Outcome.LOSE_REPUTATION,
                Outcome.LOSE_RESOURCES,
                Outcome.LOSE_COINS,
                Outcome.TRANSPORT,
                Outcome.LOSE_LEADERSHIP,
            ]
            * 1
        )
        return penalty_bag

    @classmethod
    def _difficulty_to_target_number(cls, difficulty: int) -> int:
        return difficulty * 2 + 1
