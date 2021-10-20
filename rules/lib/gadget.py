from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from picaro.rules.base import get_rules_cache
from picaro.rules.types.internal import (
    Action,
    Character,
    EntityType,
    Filter,
    Gadget,
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
        val += overlay.value
    return val


def load_available_overlays(
    entity_uuid: str,
) -> Dict[Tuple[OverlayType, Optional[str]], List[Overlay]]:
    overlays = defaultdict(list)
    for gadget in Gadget.load_all():
        for overlay in gadget.overlays:
            if overlay.is_private and gadget.entity != entity_uuid:
                continue
            overlays[(overlay.type, overlay.subtype)].append(overlay)
    return overlays


def load_available_triggers(
    entity_uuid: str,
) -> Dict[Tuple[TriggerType, Optional[str]], List[Trigger]]:
    triggers = defaultdict(list)
    for gadget in Gadget.load_all():
        for trigger in gadget.triggers:
            if trigger.is_private and gadget.entity != entity_uuid:
                continue
            triggers[(trigger.type, trigger.subtype)].append(trigger)
    return triggers


def load_available_actions(entity_uuid: str) -> List[Action]:
    actions: List[Action] = []
    for gadget in Gadget.load_all():
        for action in gadget.actions:
            if action.is_private and gadget.entity != entity_uuid:
                continue
            actions.append(action)
    return actions
