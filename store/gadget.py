import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from picaro.common.exceptions import IllegalMoveException

from .base import StandardStorage, StandardWrapper, make_double_uuid, get_parent_uuid
from .common_types import (
    Action,
    Effect,
    Filter,
    Overlay,
    OverlayType,
    Trigger,
    TriggerType,
)


@dataclass
class GadgetStorage(StandardStorage["GadgetStorage"]):
    TABLE_NAME = "gadget"

    uuid: str
    name: str
    overlays: List[Overlay]
    triggers: List[Trigger]
    actions: List[Action]
    entity: str


class Gadget(StandardWrapper[GadgetStorage]):
    @classmethod
    def load_for_entity(cls, entity: str) -> List["Gadget"]:
        return [Gadget(g) for g in GadgetStorage.load_all() if g.entity == entity]

    @classmethod
    def load_action_by_uuid(cls, uuid: str) -> "Action":
        gadget_uuid = get_parent_uuid(uuid)
        gadget_data = GadgetStorage.load(gadget_uuid)
        actions = [a for a in gadget_data.actions if a.uuid == uuid]
        if not actions:
            raise IllegalMoveException(f"No such action: {uuid}")
        return actions[0]

    def add_overlay(
        self,
        type: OverlayType,
        value: int,
        subtype: Optional[str],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add overlay to non-writable gadget")
        self.overlays.append(
            Overlay(
                uuid=make_double_uuid(self.uuid),
                value=value,
                type=type,
                subtype=subtype,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_overlay_object(self, overlay: Overlay) -> None:
        if not self._write:
            raise Exception(f"Can't add overlay to non-writable gadget")
        overlay = dataclasses.replace(overlay, uuid=make_double_uuid(self.uuid))
        self.overlays.append(overlay)

    def add_trigger(
        self,
        type: TriggerType,
        effects: Sequence[Effect],
        subtype: Optional[str],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add trigger to non-writable gadget")
        self.triggers.append(
            Trigger(
                uuid=make_double_uuid(self.uuid),
                effects=effects,
                type=type,
                subtype=subtype,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_trigger_object(self, trigger: Trigger) -> None:
        if not self._write:
            raise Exception(f"Can't add trigger to non-writable gadget")
        trigger = dataclasses.replace(trigger, uuid=make_double_uuid(self.uuid))
        self.triggers.append(trigger)

    def add_action(
        self,
        name: str,
        cost: Sequence[Effect],
        benefit: Sequence[Effect],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add action to non-writable gadget")
        self.actions.append(
            Action(
                uuid=make_double_uuid(self.uuid),
                name=name,
                cost=cost,
                benefit=benefit,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_action_object(self, action: Action) -> None:
        if not self._write:
            raise Exception(f"Can't add action to non-writable gadget")
        action = dataclasses.replace(action, uuid=make_double_uuid(self.uuid))
        self.actions.append(action)
