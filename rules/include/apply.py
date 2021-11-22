import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.storage import make_uuid
from picaro.common.utils import clamp
from picaro.rules.base import get_rules_cache
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.encounter import EncounterRules
from picaro.rules.types.external import Title
from picaro.rules.types.internal import (
    AmountEffect,
    Character,
    Effect,
    EffectType,
    EncounterContextType,
    Entity,
    FullCard,
    FullCardType,
    Game,
    LocationEffect,
    Meter,
    Overlay,
    Record,
    ResourceAmountEffect,
    Token,
    Trigger,
    TurnFlags,
)

from . import translate
from .special_cards import make_assign_xp_card, make_meter_card


@dataclass
class State:
    all_effects: Dict[EffectType, List[Effect]]
    ch: Character
    enforce_costs: bool
    records: List[Record]


class ApplierBase:
    def __init__(self, type: EffectType, name: str) -> None:
        self._type = type
        self._name = name

    def apply(self, effects: List[Effect], state: State) -> None:
        raise NotImplemented("Need to implement apply")

    def _add_effect(self, effect: Effect, state: State) -> None:
        if effect.type not in state.all_effects:
            state.all_effects[effect.type] = []
        state.all_effects[effect.type].append(effect)

    def _amount_helper(
        self,
        name: str,
        effects: List[AmountEffect],
        init_value: int,
        min_value: Optional[int],
        max_value: Optional[int],
        enforce_costs: bool,
    ) -> Tuple[int, List[str]]:
        cur_value = init_value
        comments: List[str] = []
        # - put relative adjustments first just because it seems better
        #   ("set to 3, add 1" = 3, not 4)
        # - sort by value at the end to get a consistent sort, and to
        #   ensure costs aren't paid by stuff from this turn
        for eff in sorted(effects, key=lambda e: (not e.is_absolute, e.amount)):
            if eff.is_absolute:
                cur_value = eff.amount
                comments.append(
                    effect.comment if effect.comment else f"set to {eff.amount:}"
                )
            else:
                cur_value += eff.amount
                comments.append(eff.comment if eff.comment else f"{eff.amount:+}")
            if enforce_costs and cur_value < min_value:
                raise IllegalMoveException(f"You do not have enough {name} to do this.")
        return clamp(cur_value, min=min_value, max=max_value), comments


def apply_effects(
    effects: List[Effect],
    ch: Character,
    appliers: List[ApplierBase],
    records: List[Record],
    enforce_costs: bool,
) -> None:
    state = State(
        all_effects=defaultdict(list),
        ch=ch,
        enforce_costs=enforce_costs,
        records=records,
    )
    for effect in effects:
        state.all_effects[effect.type].append(effect)
    did_any = True
    while state.all_effects and did_any:
        did_any = False
        for applier in appliers:
            app_effects = state.all_effects.pop(applier._type, None)
            if not app_effects:
                continue
            applier.apply(app_effects, state)
            did_any = True
    if state.all_effects:
        raise Exception(f"Effects remaining unprocessed: {state.all_effects}")


class AmountApplier(ApplierBase):
    def __init__(
        self,
        type: EffectType,
        name: str,
        field_name: str,
        min_value: Callable[[Character], Optional[int]] = lambda _: 0,
        max_value: Callable[[Character], Optional[int]] = lambda _: None,
    ) -> None:
        super().__init__(type, name)
        self._field_name = field_name
        self._min_value = min_value
        self._max_value = max_value

    def apply(self, effects: List[Effect], state: State) -> None:
        init_value = getattr(state.ch, self._field_name, 0)
        new_value, comments = self._amount_helper(
            self._name,
            effects,
            init_value,
            self._min_value(state.ch),
            self._max_value(state.ch),
            state.enforce_costs,
        )
        setattr(state.ch, self._field_name, new_value)
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                old_amount=init_value,
                new_amount=new_value,
                comments=comments,
            )
        )


class SubtypeAmountApplierBase(ApplierBase):
    def __init__(
        self,
        type: EffectType,
        name: str,
        field_name: str,
        subtype: str,
        min_value: Callable[[Character], Optional[int]] = lambda _: 0,
        max_value: Callable[[Character], Optional[int]] = lambda _: None,
    ) -> None:
        super().__init__(type, name)
        self._field_name = field_name
        self._subtype = subtype
        self._min_value = min_value
        self._max_value = max_value

    def apply(self, effects: List[Effect], state: State) -> None:
        grouped = defaultdict(list)
        for eff in effects:
            grouped[getattr(eff, self._subtype)].append(eff)
        for grp_name, grp_vals in grouped.items():
            if grp_name is None:
                new_value, comments = self._amount_helper(
                    self._name, grp_vals, 0, 0, None, state.enforce_costs
                )
                self._apply_no_subtype(new_value, comments, state)
                continue

            init_value = getattr(state.ch, self._field_name).get(grp_name, 0)
            new_value, comments = self._amount_helper(
                grp_name + " " + self._name,
                grp_vals,
                init_value,
                self._min_value(state.ch),
                self._max_value(state.ch),
                state.enforce_costs,
            )
            getattr(state.ch, self._field_name)[grp_name] = new_value
            state.records.append(
                Record.create_detached(
                    target_uuid=state.ch.uuid,
                    type=self._type,
                    old_amount=init_value,
                    new_amount=new_value,
                    comments=comments,
                    **{self._subtype: grp_name},
                )
            )


class XpApplier(SubtypeAmountApplierBase):
    def __init__(self):
        super().__init__(EffectType.MODIFY_XP, "skill xp", "skill_xp", "skill")

    def _apply_no_subtype(
        self, new_value: int, comments: List[str], state: State
    ) -> None:
        if new_value <= 0:
            raise Exception("Don't know how to subtract unassigned xp yet")
        state.ch.queued.append(make_assign_xp_card(state.ch, new_value))
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                skill=None,
                old_amount=0,
                new_amount=new_value,
                comments=comments,
            )
        )


class ResourceApplier(SubtypeAmountApplierBase):
    def __init__(self):
        super().__init__(
            EffectType.MODIFY_RESOURCES, "resources", "resources", "resource"
        )

    def _apply_no_subtype(
        self, new_value: int, comments: List[str], state: State
    ) -> None:
        if new_value < 0:
            self._do_discard(new_value, comments, state)
        elif new_value > 0:
            self._do_draw(new_value, comments, state)

    def _do_discard(self, new_value: int, comments: List[str], state: State) -> None:
        cur_rs = [nm for rs, cnt in state.ch.resources.items() for nm in [rs] * cnt]
        to_rm = (
            random.sample(cur_rs, new_value * -1)
            if len(cur_rs) > new_value * -1
            else cur_rs
        )
        rcs = defaultdict(int)
        for rt in to_rm:
            rcs[rt] += 1
        for rt, cnt in rcs.items():
            effect = ResourceAmountEffect(
                EffectType.MODIFY_RESOURCES,
                resource=rt,
                amount=-cnt,
                comment=f"random pick {-cnt}",
            )
            self._add_effect(effect, state)
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                resource=None,
                old_amount=0,
                new_amount=new_value,
                comments=[f"{k} x{v}" for k, v in rcs.items()],
            )
        )

    def _do_draw(self, new_value: int, comments: List[str], state: State) -> None:
        loc = Token.load_single_by_entity(state.ch.uuid).location
        comments: List[str] = []
        for _ in range(new_value):
            draw = BoardRules.draw_resource_card(loc)
            if draw.value != 0:
                effect = ResourceAmountEffect(
                    EffectType.MODIFY_RESOURCES,
                    resource=draw.type,
                    amount=draw.value,
                )
                self._add_effect(effect, state)
            comments.append(draw.name)
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                resource=None,
                old_amount=0,
                new_amount=new_value,
                comments=comments,
            )
        )


class SeparateApplierBase(ApplierBase):
    def __init__(self, type: EffectType, name: str, last_only: bool = False) -> None:
        self._type = type
        self._name = name
        self._last_only = last_only

    def apply(self, effects: List[Effect], state: State) -> None:
        if self._last_only:
            self._apply_single(effects[-1], state)
        else:
            for eff in effects:
                self._apply_single(eff, state)

    def _apply_single(self, effect: Effect, state: State) -> None:
        raise NotImplemented("Need to implement apply")


class ActivityApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.MODIFY_ACTIVITY, "activity", last_only=True)

    def _apply_single(self, effect: Effect, state: State) -> None:
        if effect.enable:
            state.ch.turn_flags.discard(TurnFlags.ACTED)
        else:
            state.ch.turn_flags.add(TurnFlags.ACTED)
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                enabled=effect.enable,
                comments=[],
            )
        )


class AddEntityApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.ADD_ENTITY, "add entity")

    def _apply_single(self, effect: Effect, state: State) -> None:
        entity, tokens, overlays, triggers, meters = translate.from_external_entity(
            effect.entity
        )
        Entity.insert([entity])
        Token.insert(tokens)
        Overlay.insert(overlays)
        Trigger.insert(triggers)
        Meter.insert(meters)

        get_rules_cache().overlays.pop(state.ch.uuid, None)
        get_rules_cache().triggers.pop(state.ch.uuid, None)

        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                entity=effect.entity,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class AddTitleApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.ADD_TITLE, "add title")

    def _apply_single(self, effect: Effect, state: State) -> None:
        overlays, triggers, meters = translate.from_external_titles(
            [effect.title], state.ch.uuid
        )
        Overlay.insert(overlays)
        Trigger.insert(triggers)
        Meter.insert(meters)

        get_rules_cache().overlays.pop(state.ch.uuid, None)
        get_rules_cache().triggers.pop(state.ch.uuid, None)

        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                title=effect.title,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class QueueEncounterApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.QUEUE_ENCOUNTER, "queue encounter")

    def _apply_single(self, effect: Effect, state: State) -> None:
        # this isn't right but probably ok for now
        context_type = EncounterContextType.ACTION
        card = EncounterRules.reify_card(effect.encounter, [], 1, context_type)
        state.ch.queued.append(card)

        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                encounter=effect.encounter,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class ModifyJobApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.MODIFY_JOB, "job", last_only=True)

    def _apply_single(self, effect: Effect, state: State) -> None:
        old_job = state.ch.job_name
        CharacterRules.switch_job(state.ch, effect.job_name)
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                old_job_name=old_job,
                new_job_name=state.ch.job_name,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class ModifyLocationApplier(SeparateApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.MODIFY_LOCATION, "location", last_only=True)

    def _apply_single(self, effect: Effect, state: State) -> None:
        old_loc = BoardRules.get_single_token_hex(state.ch.uuid).name
        BoardRules.move_token_for_entity(state.ch.uuid, effect.hex, adjacent=False)
        new_loc = BoardRules.get_single_token_hex(state.ch.uuid).name
        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                old_hex=old_loc,
                new_hex=new_loc,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class TickMeterApplier(ApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.TICK_METER, "meter")

    def apply(self, effects: List[Effect], state: State) -> None:
        grouped = defaultdict(list)
        for eff in effects:
            grouped[eff.entity_uuid].append(eff)
        for entity_uuid, grp_vals in grouped.items():
            with Meter.load_for_write(entity_uuid) as meter:
                old_value = meter.cur_value
                new_value, comments = self._amount_helper(
                    meter.name + " value",
                    grp_vals,
                    meter.cur_value,
                    meter.min_value,
                    meter.max_value,
                    state.enforce_costs,
                )
                meter.cur_value = new_value

                if meter.cur_value == meter.min_value and meter.empty_effects:
                    state.ch.queued.append(make_meter_card(state.ch, meter, False))
                elif meter.cur_value == meter.max_value and meter.full_effects:
                    state.ch.queued.append(make_meter_card(state.ch, meter, True))

            state.records.append(
                Record.create_detached(
                    target_uuid=state.ch.uuid,
                    type=self._type,
                    entity_uuid=entity_uuid,
                    old_amount=old_value,
                    new_amount=new_value,
                    comments=comments,
                )
            )


class LeadershipApplier(ApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.LEADERSHIP, "leadership challenge")

    def apply(self, effects: List[Effect], state: State) -> None:
        new_value, comments = self._amount_helper(
            self._name, effects, 0, -20, 20, state.enforce_costs
        )

        card = FullCard(
            uuid=make_uuid(),
            name="Leadership Challenge",
            desc="A challenge to (or opportunity for) your leadership.",
            type=FullCardType.SPECIAL,
            signs=[],
            data="leadership",
            annotations={"leadership_difficulty": str(new_value)},
        )
        state.ch.queued.append(card)

        state.records.append(
            Record.create_detached(
                target_uuid=state.ch.uuid,
                type=self._type,
                old_amount=0,
                new_amount=new_value,
                comments=comments,
            )
        )


class TransportApplier(ApplierBase):
    def __init__(self) -> None:
        super().__init__(EffectType.TRANSPORT, "random transport")

    def apply(self, effects: List[Effect], state: State) -> None:
        new_value, comments = self._amount_helper(
            self._name, effects, 0, 0, None, state.enforce_costs
        )

        if new_value < 1:
            return

        tp_mod = new_value // 5 + 1
        tp_min = clamp(new_value - tp_mod, min=1)
        tp_max = new_value + tp_mod
        new_hex = random.choice(
            BoardRules.find_entity_neighbors(state.ch.uuid, tp_min, tp_max)
        )
        new_location = new_hex.name
        effect = LocationEffect(
            EffectType.MODIFY_LOCATION,
            hex=new_location,
            comment=f"random {tp_min}-{tp_max} hex transport",
        )
        self._add_effect(effect, state)
