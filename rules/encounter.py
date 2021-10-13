import dataclasses
import random
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple, cast

from .character import CharacterRules
from .types.common import (
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterCheck,
    EncounterContextType,
    FullCard,
    FullCardType,
    Outcome,
)
from .types.snapshot import EncounterCommands
from .types.store import Character, Game


class EncounterRules:
    @classmethod
    def make_encounter(cls, ch: Character, card: FullCard) -> Encounter:
        if card.type == FullCardType.SPECIAL:
            card = cls._actualize_special_card(ch, card)

        rolls = []
        if card.type == FullCardType.CHALLENGE:
            for chk in card.data:
                bonus = CharacterRules.get_skill_rank(ch, chk.skill)
                roll_val = random.randint(1, 8)
                reliable_min = CharacterRules.get_reliable_skill(ch, chk.skill)
                if roll_val <= reliable_min:
                    roll_val = random.randint(1, 8)
                rolls.append(roll_val + bonus)
        elif card.type == FullCardType.CHOICE:
            if card.data.is_random:
                rolls.extend(
                    random.randint(1, len(card.data.choice_list))
                    for _ in range(card.data.max_choices)
                )
        else:
            raise Exception(f"Unknown card type: {card.type.name}")

        return Encounter(
            card=card,
            rolls=rolls,
        )

    @classmethod
    def _actualize_special_card(
        cls,
        ch: Character,
        card: FullCard,
    ) -> FullCard:
        special_type = card.data
        if special_type == "trade":
            all_resources = Game.load().resources
            card_type = FullCardType.CHOICE
            data = Choices(
                min_choices=0,
                max_choices=sum(ch.resources.values()),
                is_random=False,
                choice_list=[
                    Choice(
                        cost=[
                            Effect(
                                type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1
                            )
                        ],
                        benefit=[
                            Effect(
                                type=EffectType.MODIFY_COINS,
                                value=5,
                            )
                        ],
                        max_choices=ch.resources[rs],
                    )
                    for rs in all_resources
                    if ch.resources.get(rs, 0) > 0
                ],
                cost=[Effect(type=EffectType.MODIFY_ACTIVITY, value=-1)],
            )
        else:
            raise Exception(f"Unknown special type: {special_type}")
        return dataclasses.replace(card, type=card_type, data=data)

    @classmethod
    def perform_commands(
        cls, ch: Character, encounter: Encounter, commands: EncounterCommands
    ) -> Tuple[List[Effect], List[Effect]]:
        if commands.encounter_uuid != encounter.card.uuid:
            raise BadStateException(
                f"Command uuid {commands.encounter_uuid} mismatch with expected uuid {encounter.card.uuid}"
            )

        if encounter.card.type == FullCardType.CHALLENGE:
            checks = cast(Sequence[EncounterCheck], encounter.card.data)
            return cls._perform_challenge(
                ch,
                checks,
                encounter.rolls,
                commands,
            )
        elif encounter.card.type == FullCardType.CHOICE:
            choices = cast(Choices, encounter.card.data)
            return cls._perform_choices(
                ch,
                choices,
                encounter.rolls,
                commands.choices,
            )
        else:
            raise Exception(f"Bad card type: {encounter.card.type.name}")

    @classmethod
    def _perform_challenge(
        cls,
        ch: Character,
        checks: Sequence[EncounterCheck],
        rolls: Sequence[int],
        commands: EncounterCommands,
    ) -> Tuple[List[Effect], List[Effect]]:
        cost: List[Effect] = []
        benefit: List[Effect] = []

        rolls = list(rolls[:])
        luck_spent = 0

        # validate the commands by rerunning them (note this also updates luck)
        for adj in commands.adjusts or []:
            luck_spent += 1
            rolls[adj] += 1

        for from_c, to_c in commands.transfers or []:
            if rolls[from_c] < 2:
                raise BadStateException("From not enough for transfer")
            rolls[from_c] -= 2
            rolls[to_c] += 1

        if commands.flee:
            luck_spent += 1

        rolls = tuple(rolls)
        if (luck_spent, rolls) != (commands.luck_spent, commands.rolls):
            raise BadStateException("Computed luck/rolls doesn't match?")

        if luck_spent > 0:
            cost.append(
                Effect(
                    EffectType.MODIFY_LUCK, -luck_spent, comment="encounter commands"
                )
            )
        if commands.flee:
            return cost, benefit

        ocs = defaultdict(int)
        failures = 0

        for idx, check in enumerate(checks):
            if rolls[idx] >= check.target_number:
                ocs[check.reward] += 1
            else:
                ocs[check.penalty] += 1
                failures += 1

        mcs = defaultdict(int)

        sum_til = lambda v: (v * v + v) // 2
        for outcome, cnt in ocs.items():
            benefit.extend(cls._convert_outcome(outcome, cnt, ch, checks[0].skill))
        if failures > 0:
            benefit.append(
                Effect(
                    type=EffectType.MODIFY_XP,
                    subtype=checks[0].skill,
                    value=failures,
                )
            )

        return cost, benefit

    @classmethod
    def _convert_outcome(
        cls,
        outcome: Outcome,
        cnt: int,
        ch: Character,
        default_skill: str,
    ) -> List[Effect]:
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
        elif outcome == Outcome.GAIN_PROJECT_XP:
            raise Exception("project not supported yet")
        elif outcome == Outcome.NOTHING:
            return []
        else:
            raise Exception(f"Unknown effect: {outcome}")

    @classmethod
    def _perform_choices(
        cls,
        ch: Character,
        choices: Choices,
        rolls: List[int],
        selections: Dict[int, int],
    ) -> Tuple[List[Effect], List[Effect]]:
        cost: List[Effect] = []
        benefit: List[Effect] = []

        if choices.is_random:
            rnd = defaultdict(int)
            for v in rolls:
                rnd[v - 1] += 1
            if rnd != selections:
                raise BadStateException(
                    f"Choice should match roll for random ({rnd}, {selections})"
                )

        tot = 0
        for choice_idx, cnt in selections.items():
            if choice_idx < 0 or choice_idx >= len(choices.choice_list):
                raise BadStateException(f"Choice out of range: {choice_idx}")
            choice = choices.choice_list[choice_idx]
            tot += cnt
            if cnt < choice.min_choices:
                raise IllegalMoveException(
                    f"Must choose {choice.name or 'this'} at least {with_s(choice.min_choices, 'time')}."
                )
            if cnt > choice.max_choices:
                raise IllegalMoveException(
                    f"Must choose {choice.name or 'this'} at most {with_s(choice.max_choices, 'time')}."
                )
        if tot < choices.min_choices:
            raise IllegalMoveException(
                f"Must select at least {with_s(choices.min_choices, 'choice')}."
            )
        if tot > choices.max_choices:
            raise IllegalMoveException(
                f"Must select at most {with_s(choices.max_choices, 'choice')}."
            )

        cost.extend(choices.cost)
        benefit.extend(choices.benefit)
        for choice_idx, cnt in selections.items():
            choice = choices.choice_list[choice_idx]
            for _ in range(cnt):
                cost.extend(choice.cost)
                benefit.extend(choice.benefit)
        return cost, benefit
