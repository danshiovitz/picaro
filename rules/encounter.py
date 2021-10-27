import dataclasses
import random
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple, cast

from picaro.common.storage import make_uuid

from .character import CharacterRules
from .include.deck import shuffle_discard
from .include.special_cards import actualize_special_card
from .types.external import EncounterCommands
from .types.internal import (
    Character,
    Challenge,
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterCheck,
    EncounterContextType,
    FullCard,
    FullCardType,
    Game,
    Outcome,
    TemplateCard,
    TemplateCardType,
    TemplateDeck,
)


# Briefly about the lifecycle of an encounter:
# It starts off as a TemplateCard, which represents "the sort of stuff that happens",
# like "sometimes there are sandstorms in the desert" or "sometimes raiders raid caravans"
# * Challenges have their list of typical skills and rewards
# * Choices have their list of choices
# * Specials just have their special type
# Then it becomes a FullCard, which represents a specific thing, like "there's a sandstorm
# in hex AE05"
# * Challenges have a list of specific checks, with the skill, tn, reward, and penalty picked
# * Choices have their list of choices (you could imagine templated choices that get
#   narrowed down, but those don't exist for now)
# * Specials are still left as their special type
# The FullCard goes into the tableau, or directly into a character's queue
# Eventually it gets to the front of the queue and becomes an Encounter, which represents
# "what the character is doing right now"
# * Challenges get the die roll assigned for each check
# * Choices get a random roll if they are a random choice
# * Specials get converted into challenge or choice and then as above. We do this so that,
#   eg, the trade special can go off what the character has in inventory right now.
class EncounterRules:
    @classmethod
    def load_deck(cls, name: str) -> List[TemplateCard]:
        template_deck = TemplateDeck.load(name)
        return shuffle_discard(
            c
            for idx, c in enumerate(template_deck.cards)
            for _ in range(template_deck.copies[idx])
        )

    @classmethod
    def reify_card(
        cls,
        val: TemplateCard,
        base_skills: Sequence[str],
        difficulty: int,
        context_type: EncounterContextType,
    ) -> FullCard:
        game = Game.load()
        base_skills = list(base_skills)

        if val.type == TemplateCardType.CHOICE:
            data = cls._make_choices(cast(Choices, val.data))
            card_type = FullCardType.CHOICE
        elif val.type == TemplateCardType.CHALLENGE:
            data = cls._make_challenge(
                cast(Challenge, val.data), base_skills, difficulty, context_type
            )
            card_type = FullCardType.CHALLENGE
        elif val.type == TemplateCardType.SPECIAL:
            data = val.data
            card_type = FullCardType.SPECIAL
        else:
            raise Exception(f"Unknown card type {val.type.name}")

        signs = random.sample(game.zodiacs, 2)

        return FullCard(
            uuid=make_uuid(),
            name=val.name,
            desc=val.desc,
            type=card_type,
            data=data,
            signs=signs,
            annotations=val.annotations,
        )

    @classmethod
    def _make_challenge(
        cls,
        challenge: Challenge,
        base_skills: Sequence[str],
        difficulty: int,
        context_type: EncounterContextType,
    ) -> Sequence[EncounterCheck]:
        game = Game.load()
        skill_bag = []
        # the number of copies of the core skills only matters on the third check,
        # where we add in all the skills (let's assume there are 36) and want to
        # have the copy number such that we pick a core skill (let's assume there
        # are 6) say 50% of the time and an unusual skill 50% of the time
        sk = (list(challenge.skills) + base_skills + base_skills)[0:6]
        skill_bag.extend(sk * 6)

        reward_bag = cls._make_reward_bag(challenge, context_type)
        penalty_bag = cls._make_penalty_bag(challenge, context_type)
        return [
            cls._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
            cls._make_check(difficulty, skill_bag, reward_bag, penalty_bag),
            cls._make_check(
                difficulty,
                skill_bag + list(game.skills),
                reward_bag,
                penalty_bag,
            ),
        ]

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
        skill = random.choice(skill_bag)
        return EncounterCheck(
            skill=skill,
            modifier=None,
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
                Outcome.LOSE_SPEED,
            ]
            * 1
        )
        return penalty_bag

    @classmethod
    def _difficulty_to_target_number(cls, difficulty: int) -> int:
        return difficulty * 2 + 1

    @classmethod
    def _make_choices(cls, choices: Choices) -> Choices:
        if choices.max_choices <= 0:
            # implies: do a random selection, weighted by the individual max choices
            idxs = [
                v
                for idx, c in enumerate(choices.choice_list)
                for v in [idx] * c.max_choices
            ]
            idx = random.choice(idxs)
            choices = dataclasses.replace(
                choices, max_choices=1, choice_list=[choices.choice_list[idx]]
            )
        return choices

    @classmethod
    def make_encounter(cls, ch: Character, card: FullCard) -> Encounter:
        if card.type == FullCardType.SPECIAL:
            card = actualize_special_card(ch, card)

        rolls = []
        if card.type == FullCardType.CHALLENGE:
            for chk in card.data:
                bonus = CharacterRules.get_skill_rank(ch, chk.skill)
                roll_vals = [random.randint(1, 8)]
                reliable_min = CharacterRules.get_reliable_skill(ch, chk.skill)
                if roll_vals[0] <= reliable_min:
                    roll_vals.append(random.randint(1, 8))
                rolls.append([rv + bonus for rv in roll_vals])
        elif card.type == FullCardType.CHOICE:
            pass
        else:
            raise Exception(f"Unknown card type: {card.type.name}")

        return Encounter(
            card=card,
            rolls=rolls,
        )

    @classmethod
    def convert_outcome(
        cls,
        outcome: Outcome,
        cnt: int,
        ch: Character,
        card: FullCard,
    ) -> List[Effect]:
        if card.type != FullCardType.CHALLENGE:
            raise Exception("convert_outcome called with non-challenge")
        checks = cast(Sequence[EncounterCheck], card.data)
        default_skill = card.data[0].skill
        sum_til = lambda v: (v * v + v) // 2
        if outcome == Outcome.GAIN_COINS:
            return [Effect(type=EffectType.MODIFY_COINS, value=sum_til(cnt))]
        elif outcome == Outcome.LOSE_COINS:
            return [Effect(type=EffectType.MODIFY_COINS, value=-cnt)]
        elif outcome == Outcome.GAIN_REPUTATION:
            return [Effect(type=EffectType.MODIFY_REPUTATION, value=sum_til(cnt))]
        elif outcome == Outcome.LOSE_REPUTATION:
            return [Effect(type=EffectType.MODIFY_REPUTATION, value=-cnt)]
        elif outcome == Outcome.GAIN_HEALING:
            return [Effect(type=EffectType.MODIFY_HEALTH, value=cnt * 3)]
        elif outcome == Outcome.DAMAGE:
            return [Effect(type=EffectType.MODIFY_HEALTH, value=-sum_til(cnt))]
        elif outcome == Outcome.GAIN_XP:
            return [
                Effect(type=EffectType.MODIFY_XP, subtype=default_skill, value=cnt * 5)
            ]
        elif outcome == Outcome.GAIN_RESOURCES:
            return [Effect(type=EffectType.MODIFY_RESOURCES, value=cnt)]
        elif outcome == Outcome.LOSE_RESOURCES:
            return [Effect(type=EffectType.MODIFY_RESOURCES, value=-cnt)]
        elif outcome == Outcome.GAIN_TURNS:
            return [Effect(type=EffectType.MODIFY_TURNS, value=cnt)]
        elif outcome == Outcome.LOSE_TURNS:
            return [Effect(type=EffectType.MODIFY_TURNS, value=-cnt)]
        elif outcome == Outcome.GAIN_SPEED:
            return [Effect(type=EffectType.MODIFY_SPEED, value=cnt * 2)]
        elif outcome == Outcome.LOSE_SPEED:
            return [Effect(type=EffectType.MODIFY_SPEED, value=-cnt)]
        elif outcome == Outcome.TRANSPORT:
            return [Effect(type=EffectType.TRANSPORT, value=cnt * 5)]
        elif outcome == Outcome.LOSE_LEADERSHIP:
            return [Effect(type=EffectType.LEADERSHIP, value=-cnt)]
        elif outcome == Outcome.NOTHING:
            return []
        else:
            raise Exception(f"Unknown effect: {outcome}")
