from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from picaro.rules.base import get_rules_cache
from picaro.rules.types.internal import (
    Character,
    Effect,
    EffectType,
    EntityType,
    Filter,
    Overlay,
    OverlayType,
    Trigger,
    TriggerType,
)


def compute_overlay_value(
    entity_uuid: str,
    type: OverlayType,
    subtype: Optional[str],
    filter_func: Callable[[Filter], bool],
) -> int:
    rules_cache = get_rules_cache()
    if entity_uuid not in rules_cache.overlays:
        rules_cache.overlays[entity_uuid] = load_available_overlays(entity_uuid)
    overlays = rules_cache.overlays[entity_uuid]

    overlay_list = []
    if subtype is not None:
        overlay_list.extend(overlays.get((type, None), []))
    overlay_list.extend(overlays.get((type, subtype), []))
    val = 0

    for overlay in overlay_list:
        if overlay.uuid in rules_cache.in_use_overlays:
            continue
        try:
            rules_cache.in_use_overlays.add(overlay.uuid)
            if not all(filter_func(f) for f in overlay.filters):
                continue
        finally:
            rules_cache.in_use_overlays.discard(overlay.uuid)
        val += overlay.amount
    return val


def load_available_overlays(
    entity_uuid: str,
) -> Dict[Tuple[OverlayType, Optional[str]], List[Overlay]]:
    overlays = defaultdict(list)
    for overlay in Overlay.load_visible_for_entity(entity_uuid):
        subtype = None
        if hasattr(overlay, "skill"):
            subtype = overlay.skill
        elif hasattr(overlay, "hex"):
            subtype = overlay.hex
        elif hasattr(overlay, "resource"):
            subtype = overlay.resource
        overlays[(overlay.type, subtype)].append(overlay)
    return overlays


def compute_trigger_effects(
    entity_uuid: str,
    type: TriggerType,
    subtype: Optional[str],
    filter_func: Callable[[Filter], bool],
) -> List[Effect]:
    rules_cache = get_rules_cache()
    if entity_uuid not in rules_cache.triggers:
        rules_cache.triggers[entity_uuid] = load_available_triggers(entity_uuid)
    triggers = rules_cache.triggers[entity_uuid]

    trigger_list = []
    if subtype is not None:
        trigger_list.extend(triggers.get((type, None), []))
    trigger_list.extend(triggers.get((type, subtype), []))

    effects: List[Effect] = []

    for trigger in trigger_list:
        if not all(filter_func(f) for f in trigger.filters):
            continue
        effects.extend(trigger.effects)
    return effects


def load_available_triggers(
    entity_uuid: str,
) -> Dict[Tuple[TriggerType, Optional[str]], List[Trigger]]:
    triggers = defaultdict(list)
    for trigger in Trigger.load_visible_for_entity(entity_uuid):
        subtype = None
        if hasattr(trigger, "skill"):
            subtype = trigger.skill
        elif hasattr(trigger, "resource"):
            subtype = trigger.resource
        elif hasattr(trigger, "hex"):
            subtype = trigger.hex
        triggers[(trigger.type, subtype)].append(trigger)
    return triggers


def compute_actions(entity_uuid: str) -> List[Trigger]:
    rules_cache = get_rules_cache()
    if entity_uuid not in rules_cache.triggers:
        rules_cache.triggers[entity_uuid] = load_available_triggers(entity_uuid)
    triggers = rules_cache.triggers[entity_uuid]
    return triggers.get((TriggerType.ACTION, None), [])
