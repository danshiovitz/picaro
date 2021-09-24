import random
from dataclasses import dataclass
from typing import Generic, List, Optional, Sequence, Tuple, TypeVar, cast

from .exceptions import IllegalMoveException
from .game import load_game
from .storage import ObjectStorageBase
from .types import (
    Challenge,
    Choices,
    EncounterCheck,
    EncounterContextType,
    Outcome,
    FullCard,
    FullCardType,
    TemplateCard,
    TemplateCardType,
    TemplateDeck,
    make_id,
)


def actualize_deck(
    deck: TemplateDeck,
    difficulty: int,
    context: EncounterContextType,
    additional: List[TemplateCard] = None,
) -> List[FullCard]:
    ret = []
    for tmpl in semi_actualize_deck(deck, additional):
        ret.append(make_card(deck, tmpl, difficulty, context))
    return ret


def semi_actualize_deck(
    deck: TemplateDeck, additional: List[TemplateCard] = None
) -> List[TemplateCard]:
    ret = []
    for tmpl in list(deck.templates) + (additional or []):
        for _ in range(tmpl.copies):
            ret.append(tmpl)
    random.shuffle(ret)
    for _ in range((len(ret) // 10) + 1):
        ret.pop()
    return ret


def make_card(
    deck: Optional[TemplateDeck],
    val: TemplateCard,
    difficulty: int,
    context_type: EncounterContextType,
) -> FullCard:
    if val.type == TemplateCardType.CHOICE:
        data = val.data
        card_type = FullCardType.CHOICE
    elif val.type == TemplateCardType.CHALLENGE:
        if not deck:
            raise Exception("Can't make challenge card with no deck")
        challenge = cast(Challenge, val.data)
        skill_bag = []
        # the number of copies of the core skills only matters on the third check,
        # where we add in all the skills (let's assume there are 36) and want to
        # have the copy number such that we pick a core skill (let's assume there
        # are 6) say 50% of the time and an unusual skill 50% of the time
        sk = (list(challenge.skills) + list(deck.base_skills) + list(deck.base_skills))[
            0:6
        ]
        skill_bag.extend(sk * 6)

        all_skills = list(load_game().skills)
        reward_bag = _make_reward_bag(deck, challenge, context_type)
        penalty_bag = _make_penalty_bag(deck, challenge, context_type)
        if challenge.difficulty is not None:
            difficulty = challenge.difficulty
        data = [
            _make_check(deck, difficulty, skill_bag, reward_bag, penalty_bag),
            _make_check(deck, difficulty, skill_bag, reward_bag, penalty_bag),
            _make_check(
                deck,
                difficulty,
                skill_bag + all_skills,
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

    all_zodiacs = load_game().zodiacs
    signs = random.sample(all_zodiacs, 2) if not val.unsigned else []

    card_id = make_id()
    return FullCard(
        id=card_id,
        name=val.name,
        desc=val.desc,
        type=card_type,
        data=data,
        signs=signs,
        context_type=context_type,
        entity_type=val.entity_type,
        entity_name=val.entity_name,
    )


def _make_check(
    deck: TemplateDeck,
    difficulty: int,
    skill_bag: List[str],
    reward_bag: List[Outcome],
    penalty_bag: List[Outcome],
) -> EncounterCheck:
    tn = _difficulty_to_target_number(deck, difficulty)
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
    deck: TemplateDeck, challenge: Challenge, context: EncounterContextType
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


def _make_penalty_bag(
    deck: TemplateDeck, challenge: Challenge, context: EncounterContextType
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


def _difficulty_to_target_number(deck: TemplateDeck, difficulty: int) -> int:
    return difficulty * 2 + 1


def load_deck(deck_name: str) -> TemplateDeck:
    return TemplateDeckStorage.load_by_name(deck_name)


def create_decks(
    decks: List[TemplateDeck],
) -> None:
    TemplateDeckStorage.insert(decks)


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

    @classmethod
    def insert(cls, decks: List[TemplateDeck]) -> None:
        cls._insert_helper(decks)
