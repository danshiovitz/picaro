import random
from typing import Dict, List, Optional, Tuple

from picaro.common.storage import make_uuid
from picaro.common.utils import clamp
from picaro.rules.base import get_rules_cache
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.encounter import EncounterRules
from picaro.rules.types.external import Title
from picaro.rules.types.internal import (
    Character,
    Effect,
    EffectType,
    EncounterContextType,
    Entity,
    FullCard,
    FullCardType,
    Game,
    Meter,
    Overlay,
    Record,
    Token,
    Trigger,
    TurnFlags,
)

from . import translate
from .apply import Field, IntField
from .special_cards import make_assign_xp_card, make_meter_card


class LeadershipMetaField(IntField):
    def __init__(self) -> None:
        super().__init__(
            "leadership challenge",
            EffectType.LEADERSHIP,
            None,
            init_v=lambda e: 0,
            set_v=self._do_disrupt,
            min_value=lambda _: -20,
            max_value=lambda _: 20,
        )

    def _do_disrupt(self, ch: Character, val: int) -> bool:
        card = FullCard(
            uuid=make_uuid(),
            name="Leadership Challenge",
            desc="A challenge to (or opportunity for) your leadership.",
            type=FullCardType.SPECIAL,
            signs=[],
            data="leadership",
            annotations={"leadership_difficulty": str(val)},
        )
        ch.queued.append(card)
        return True


class ModifyJobField(Field):
    def __init__(self) -> None:
        super().__init__("job", EffectType.MODIFY_JOB, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        # don't actually switch multiple times
        if not is_last:
            return
        old_job = self._ch.job_name
        CharacterRules.switch_job(self._ch, effect.value)
        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=old_job,
                new_value=self._ch.job_name,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class ResourceDrawMetaField(IntField):
    def __init__(self) -> None:
        super().__init__(
            "resource draws",
            EffectType.MODIFY_RESOURCES,
            None,
            init_v=lambda e: 0,
            set_v=self._do_both,
        )

    def _do_both(self, ch: Character, val: int) -> bool:
        if val < 0:
            self._do_discard(ch, val)
        elif val > 0:
            self._do_draw(ch, val)
        # if == 0, do nothing
        return False

    def _do_discard(self, ch: Character, val: int) -> None:
        cur_rs = [nm for rs, cnt in self._ch.resources.items() for nm in [rs] * cnt]
        to_rm = random.sample(cur_rs, val * -1) if len(cur_rs) > val * -1 else cur_rs
        rcs = defaultdict(int)
        for rt in to_rm:
            rcs[rt] += 1
        for rt, cnt in rcs.items():
            self._split_effects[(EffectType.MODIFY_RESOURCES, rt)].append(
                Effect(
                    EffectType.MODIFY_RESOURCES,
                    -cnt,
                    subtype=rt,
                    comment=f"random pick {-cnt}",
                )
            )
        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=0,
                new_value=val,
                comments=[f"{k} x{v}" for k, v in rcs.items()],
            )
        )

    def _do_draw(self, ch: Character, val: int) -> None:
        loc = Token.load_single_by_entity(self._ch.uuid).location
        comments = []
        for _ in range(val):
            draw = BoardRules.draw_resource_card(loc)
            if draw.value != 0:
                self._split_effects[(EffectType.MODIFY_RESOURCES, draw.type)].append(
                    Effect(
                        EffectType.MODIFY_RESOURCES,
                        draw.value,
                        subtype=draw.type,
                    )
                )
            comments.append(draw.name)
        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=0,
                new_value=val,
                comments=comments,
            )
        )


class TransportField(IntField):
    def __init__(self) -> None:
        super().__init__(
            "transport",
            EffectType.TRANSPORT,
            None,
            init_v=lambda e: 0,
            set_v=self._do_transport,
        )

    def _do_transport(self, ch: Character, val: int) -> None:
        tp_mod = val // 5 + 1
        tp_min = clamp(val - tp_mod, min=1)
        tp_max = val + tp_mod
        new_hex = random.choice(
            BoardRules.find_entity_neighbors(self._ch.uuid, tp_min, tp_max)
        )
        new_location = new_hex.name
        self._split_effects[(EffectType.MODIFY_LOCATION, None)].append(
            Effect(
                EffectType.MODIFY_LOCATION,
                new_location,
                comment=f"random {tp_min}-{tp_max} hex transport",
            )
        )
        return False  # modify_location will record appropriately


class ModifyLocationField(Field):
    def __init__(self) -> None:
        super().__init__("location", EffectType.MODIFY_LOCATION, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        # don't actually switch multiple times
        if not is_last:
            return
        old_loc = BoardRules.get_single_token_hex(self._ch.uuid).name
        BoardRules.move_token_for_entity(self._ch.uuid, effect.value, adjacent=False)
        new_loc = BoardRules.get_single_token_hex(self._ch.uuid).name
        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=old_loc,
                new_value=new_loc,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class ModifyActivityField(IntField):
    def __init__(self) -> None:
        super().__init__(
            "available activity",
            EffectType.MODIFY_ACTIVITY,
            None,
            init_v=lambda _: 0 if TurnFlags.ACTED in self._ch.turn_flags else 1,
            set_v=self._do_action,
        )

    def _do_action(self, ch: Character, val: int) -> None:
        if val <= 0:
            self._ch.turn_flags.add(TurnFlags.ACTED)
        else:
            self._ch.turn_flags.discard(TurnFlags.ACTED)
        return True


class AddEntityField(Field):
    def __init__(self) -> None:
        super().__init__("entity", EffectType.ADD_ENTITY, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        entity, tokens, overlays, triggers, meters = translate.from_external_entity(
            effect.value
        )
        Entity.insert([entity])
        Token.insert(tokens)
        Overlay.insert(overlays)
        Trigger.insert(triggers)
        Meter.insert(meters)

        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=None,
                new_value=effect.value,
                comments=[effect.comment] if effect.comment else [],
            )
        )
        get_rules_cache().overlays.pop(self._ch.uuid, None)
        get_rules_cache().triggers.pop(self._ch.uuid, None)


class AddTitleField(Field):
    def __init__(self):
        super().__init__("titles", EffectType.ADD_TITLE, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        overlays, triggers, meters = translate.from_external_titles(
            [effect.value], self._ch.uuid
        )
        Overlay.insert(overlays)
        Trigger.insert(triggers)
        Meter.insert(meters)

        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=None,
                new_value=effect.value,
                comments=[effect.comment] if effect.comment else [],
            )
        )
        get_rules_cache().overlays.pop(self._ch.uuid, None)
        get_rules_cache().triggers.pop(self._ch.uuid, None)


class QueueEncounterField(Field):
    def __init__(self) -> None:
        super().__init__("encounter", EffectType.QUEUE_ENCOUNTER, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        template = effect.value
        # this isn't right but probably ok for now
        context_type = EncounterContextType.ACTION
        card = EncounterRules.reify_card(template, [], 1, context_type)
        self._ch.queued.append(card)
        self._records.append(
            Record.create_detached(
                entity_uuid=self._ch.uuid,
                type=self._type,
                subtype=self._subtype,
                old_value=None,
                new_value=template,
                comments=[effect.comment] if effect.comment else [],
            )
        )


class ModifyFreeXpField(IntField):
    def __init__(self) -> None:
        super().__init__(
            "free xp",
            EffectType.MODIFY_XP,
            None,
            init_v=lambda e: 0,
            set_v=self._do_modify,
        )

    def _do_modify(self, ch: Character, val: int) -> None:
        if val <= 0:
            raise Exception("Don't know how to subtract unassigned xp yet")
        self._ch.queued.append(make_assign_xp_card(ch, val))
        return True


class TickMeterField(IntField):
    def __init__(self, subtype: str) -> None:
        super().__init__(
            "meter",
            EffectType.TICK_METER,
            subtype,
            init_v=self._get_init_value,
            set_v=self._do_modify,
            min_value=self._get_min_value,
            max_value=self._get_max_value,
        )

    def _get_init_value(self, ch: Character) -> int:
        meter = Meter.load(self._subtype)
        return meter.cur_value

    def _get_min_value(self, ch: Character) -> Optional[int]:
        meter = Meter.load(self._subtype)
        return meter.min_value

    def _get_max_value(self, ch: Character) -> Optional[int]:
        meter = Meter.load(self._subtype)
        return meter.max_value

    def _do_modify(self, ch: Character, val: int) -> None:
        with Meter.load_for_write(self._subtype) as meter:
            meter.cur_value = val
            if meter.cur_value == meter.min_value and meter.empty_effects:
                ch.queued.append(make_meter_card(ch, meter, False))
            elif meter.cur_value == meter.max_value and meter.full_effects:
                ch.queued.append(make_meter_card(ch, meter, True))
        return True

    @classmethod
    def make_fields(
        cls,
        split_effects: Dict[Tuple[EffectType, Optional[str]], List[Effect]],
    ) -> List[Field]:
        subtypes = [
            k[1]
            for k in split_effects
            if k[0] == EffectType.TICK_METER and k[1] is not None
        ]
        return [cls(subtype) for subtype in subtypes]
