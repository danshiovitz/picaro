import dataclasses
from types import MappingProxyType
from typing import Any

from picaro.common.storage import make_uuid
from picaro.rules.character import CharacterRules
from picaro.rules.types.external import Title
from picaro.rules.types.internal import (
    Character,
    Choice,
    Choices,
    Effect,
    EffectType,
    EncounterCheck,
    FullCard,
    FullCardType,
    Game,
    Job,
    Outcome,
    Overlay,
    OverlayType,
    TurnFlags,
)


def queue_bad_reputation_check(ch: Character) -> None:
    if ch.reputation > 0:
        return

    if ch.check_set_flag(TurnFlags.BAD_REP_CHECKED):
        return

    choice_list = [
        Choice(effects=(Effect(type=EffectType.LEADERSHIP, subtype=None, value=-1),)),
    ]

    card = FullCard(
        uuid=make_uuid(),
        name="Bad Reputation",
        desc="Automatic job check at zero reputation.",
        type=FullCardType.CHOICE,
        signs=[],
        data=Choices(
            min_choices=1,
            max_choices=1,
            choice_list=choice_list,
        ),
    )
    ch.queued.append(card)


def queue_discard_resources(ch: Character) -> None:
    # discard down to correct number of resources
    overage = sum(ch.resources.values()) - CharacterRules.get_max_resources(ch)
    if overage <= 0:
        return

    choice_list = [
        Choice(
            costs=(Effect(type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1),),
            max_choices=cnt,
        )
        for rs, cnt in ch.resources.items()
        if cnt > 0
    ]

    card = FullCard(
        uuid=make_uuid(),
        name="Discard Resources",
        desc=f"You must discard to {CharacterRules.get_max_resources(ch)} resources.",
        type=FullCardType.CHOICE,
        signs=[],
        data=Choices(
            min_choices=overage,
            max_choices=overage,
            choice_list=choice_list,
        ),
    )
    ch.queued.append(card)


def make_promo_card(ch: Character, job_name: str) -> FullCard:
    job = Job.load(job_name)

    # first title is empty (+xp), then others give reliable overlay
    title_effects = [[]]
    for sk in job.base_skills:
        title_effects.append(
            [
                Overlay(
                    uuid="",
                    type=OverlayType.RELIABLE_SKILL,
                    subtype=sk,
                    value=1,
                    is_private=True,
                    filters=[],
                )
            ],
        )
    titles = [
        Title(
            name=f"Veteran {job_name}",
            overlays=ee,
            triggers=[],
            actions=[],
        )
        for ee in title_effects
    ]
    extra = [[] for ee in titles]
    extra[0].append(Effect(type=EffectType.MODIFY_XP, subtype=None, value=10))
    choice_list = [
        Choice(effects=tuple([Effect(type=EffectType.ADD_TITLE, value=e)] + xt))
        for e, xt in zip(titles, extra)
    ]

    return FullCard(
        uuid=make_uuid(),
        name="Job Promotion",
        desc=f"Select a benefit for being promoted from {job_name}.",
        type=FullCardType.CHOICE,
        signs=[],
        data=Choices(
            min_choices=0,
            max_choices=1,
            choice_list=choice_list,
        ),
    )


def make_assign_xp_card(ch: Character, amount: int) -> FullCard:
    return FullCard(
        uuid=make_uuid(),
        name="Assign XP",
        desc=f"Assign {amount} xp",
        type=FullCardType.CHOICE,
        signs=[],
        data=Choices(
            min_choices=0,
            max_choices=1,
            choice_list=[
                Choice(
                    effects=(
                        Effect(type=EffectType.MODIFY_XP, subtype=sk, value=amount),
                    )
                )
                for sk in Game.load().skills
            ],
        ),
    )


def actualize_special_card(
    ch: Character,
    card: FullCard,
) -> FullCard:
    special_type = card.data
    if special_type == "trade":
        return _actualize_trade_card(ch, card)
    elif special_type == "leadership":
        return _actualize_leadership_card(ch, card)
    else:
        raise Exception(f"Unknown special type: {special_type}")


def _actualize_trade_card(
    ch: Character,
    card: FullCard,
) -> FullCard:
    all_resources = Game.load().resources
    data = Choices(
        min_choices=0,
        max_choices=sum(ch.resources.values()),
        choice_list=[
            Choice(
                costs=[Effect(type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1)],
                effects=[
                    Effect(
                        type=EffectType.MODIFY_COINS,
                        value=CharacterRules.get_trade_price(ch, rs),
                    )
                ],
                max_choices=ch.resources[rs],
            )
            for rs in all_resources
            if ch.resources.get(rs, 0) > 0
        ],
        costs=[Effect(type=EffectType.MODIFY_ACTIVITY, value=-1)],
    )
    return dataclasses.replace(card, type=FullCardType.CHOICE, data=data)


def _actualize_leadership_card(
    ch: Character,
    card: FullCard,
) -> FullCard:
    difficulty = int(card.annotations.get("leadership_difficulty", "0"))
    target_number = 4 - difficulty
    rolls = 1 + (ch.reputation // 4)

    # if they only roll 1 die, it's impossible to get a success, which sucks
    if rolls == 1:
        target_number += 1
        rolls += 1

    data = [
        EncounterCheck(
            skill="Leadership",
            modifier=0,
            target_number=target_number,
            reward=Outcome.VICTORY,
            penalty=Outcome.NOTHING,
        )
        for _ in range(rolls)
    ]
    annotations = {k: v for k, v in card.annotations.items()}
    annotations["victory"] = "leadership"
    return dataclasses.replace(
        card,
        type=FullCardType.CHALLENGE,
        data=data,
        annotations=MappingProxyType(annotations),
    )
