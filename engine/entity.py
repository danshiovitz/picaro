from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from picaro.common.utils import clamp

from .exceptions import BadStateException, IllegalMoveException
from .types import Effect, EffectType, EntityType, Event, make_id

# the assumed usage of these classes is something like
#   coins_maker = lambda: IntEntityField(EffectType.MODIFY_COINS, None, ...)
#   coins_instance = coins_maker()
# ie, the thing is initialized with common fields, but we make a new instance
# for each apply_effects call so it can have local variables
class EntityField:
    def __init__(self, name: str, type: EffectType, subtype: Optional[str]) -> None:
        self._name = name
        self._type = type
        self._subtype = subtype
        self._comments: List[str] = []

    def apply_single(
        self,
        entity: "Entity",
        split_effects: Dict[Tuple[EntityType, Optional[str]], List[Effect]],
        events: List[Event],
    ) -> None:
        effects = split_effects.pop((self._type, self._subtype), [])
        if not effects:
            return
        self._entity = entity
        self._split_effects = split_effects
        self._events = events
        # put costs first to ensure they're paid up front and not with stuff from this turn
        # put relative adjustments first just because it seems better ("set to 3, add 1" = 3, not 4)
        # sort by value at the end just to get a consistent sort
        effects = sorted(
            effects, key=lambda e: (not e.is_cost, not e.is_absolute, e.value)
        )
        for idx, effect in enumerate(effects):
            if effect.type != self._type or effect.subtype != self._subtype:
                raise Exception(
                    f"Unexpected effect: got {effect.type},{effect.subtype} - wanted {self._type},{self._subtype}"
                )
            self._update(effect, idx == 0, idx == len(effects) - 1)

    def _update(self, effect: Effect, is_first: bool, is_last: bool) -> None:
        pass


class IntEntityField(EntityField):
    def __init__(
        self,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        init_v: Callable[["Entity"], int],
        set_v: Callable[["Entity", int], bool],
        min_value: Callable[["Entity"], Optional[int]] = lambda _: 0,
        max_value: Callable[["Entity"], Optional[int]] = lambda _: None,
    ) -> None:
        super().__init__(name, type, subtype)
        self._init_v = init_v
        self._set_v = set_v
        self._min_value = min_value
        self._max_value = max_value

    def _update(self, effect: Effect, is_first: bool, is_last: bool) -> None:
        if is_first:
            self._init_value = self._init_v(self._entity)
            self._cur_value = self._init_value
        if effect.is_absolute:
            self._cur_value = effect.value
            self._comments.append(
                effect.comment if effect.comment else f"set to {effect.value:}"
            )
        else:
            self._cur_value += effect.value
            self._comments.append(
                effect.comment if effect.comment else f"{effect.value:+}"
            )
        if effect.is_cost and self._cur_value < 0:
            raise IllegalMoveException(
                f"You do not have enough {self._name} to do this."
            )
        if is_last:
            self._finish()

    def _finish(self) -> None:
        self._cur_value = clamp(
            self._cur_value,
            min=self._min_value(self._entity),
            max=self._max_value(self._entity),
        )
        if self._cur_value == self._init_value and not self._comments:
            return
        add_event = self._set_v(self._entity, self._cur_value)
        if add_event:
            self._events.append(
                Event(
                    make_id(),
                    self._entity.ENTITY_TYPE,
                    self._entity.name,
                    self._type,
                    self._subtype,
                    self._init_value,
                    self._cur_value,
                    self._comments,
                )
            )


class SimpleIntEntityField(IntEntityField):
    def __init__(
        self,
        display_name: str,
        field_name: str,
        type: EffectType,
        subtype: Optional[str] = None,
        min_value: Callable[["Entity"], Optional[int]] = lambda _: 0,
        max_value: Callable[["Entity"], Optional[int]] = lambda _: None,
    ) -> None:
        if subtype is not None:
            raise Exception(
                f"Subtype should be none for field {field_name}, but is {subtype}"
            )

        init_v = lambda e: getattr(e._data, field_name)

        def set_v(entity: Entity, val: int) -> None:
            setattr(entity._data, field_name, val)
            return True

        super().__init__(
            display_name, type, subtype, init_v, set_v, min_value, max_value
        )


class SimpleDictIntEntityField(IntEntityField):
    def __init__(
        self,
        display_name: str,
        field_name: str,
        type: EffectType,
        subtype: Optional[str],
        min_value: Callable[["Entity"], Optional[int]] = lambda _: 0,
        max_value: Callable[["Entity"], Optional[int]] = lambda _: None,
    ) -> None:
        if subtype is None:
            raise Exception(f"Subtype should be non-none for field {field_name}")

        init_v = lambda e: getattr(e._data, field_name).get(subtype, 0)

        def set_v(entity: Entity, val: int) -> None:
            d = getattr(entity._data, field_name)
            d[subtype] = val
            return True

        super().__init__(
            display_name, type, subtype, init_v, set_v, min_value, max_value
        )

    @classmethod
    def make_fields(
        cls,
        split_effects: Dict[Tuple[EntityType, Optional[str]], List[Effect]],
        name_pfx: str,
        field_name: str,
        type: EffectType,
        **kwargs,
    ) -> List[EntityField]:
        subtypes = [k[1] for k in split_effects if k[0] == type and k[1] is not None]
        return [
            cls(f"{subtype} {name_pfx}", field_name, type, subtype, **kwargs)
            for subtype in subtypes
        ]


class Entity:
    ENTITY_TYPE: EntityType
    FIELDS: List[Callable[[], List[EntityField]]]

    def apply_effects(
        self,
        effects: List[Effect],
        events: List[Event],
    ) -> None:
        effects_split = defaultdict(list)
        for effect in effects:
            effects_split[(effect.type, effect.subtype)].append(effect)
        ffs = []
        for field_func in self.FIELDS:
            for f in field_func(effects_split):
                ffs.append((f._type, f._subtype))
                f.apply_single(self, effects_split, events)
        if effects_split:
            raise Exception(f"Effects remaining unprocessed ({ffs}): {effects_split}")
