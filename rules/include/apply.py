from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.utils import clamp
from picaro.rules.types.internal import Character, Effect, EffectType, Record, TurnFlags


# the assumed usage of these classes is something like
#   coins_maker = lambda: IntField(EffectType.MODIFY_COINS, None, ...)
#   coins_instance = coins_maker()
# ie, the thing is initialized with common fields, but we make a new instance
# for each apply_effects call so it can have local variables
class Field:
    def __init__(self, name: str, type: EffectType, subtype: Optional[str]) -> None:
        self._name = name
        self._type = type
        self._subtype = subtype
        self._comments: List[str] = []

    def apply_single(
        self,
        ch: Character,
        split_effects: Dict[Tuple[EffectType, Optional[str]], List[Effect]],
        records: List[Record],
        enforce_costs: bool,
    ) -> None:
        effects = split_effects.pop((self._type, self._subtype), [])
        if not effects:
            return
        self._ch = ch
        self._split_effects = split_effects
        self._records = records
        # - put relative adjustments first just because it seems better
        #   ("set to 3, add 1" = 3, not 4)
        # - sort by value at the end to get a consistent sort, and to
        #   ensure costs aren't paid by stuff from this turn
        effects = sorted(effects, key=lambda e: (not e.is_absolute, e.value))
        for idx, effect in enumerate(effects):
            if effect.type != self._type or effect.subtype != self._subtype:
                raise Exception(
                    f"Unexpected effect: got {effect.type},{effect.subtype} - wanted {self._type},{self._subtype}"
                )
            self._update(effect, idx == 0, idx == len(effects) - 1, enforce_costs)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        pass


class IntField(Field):
    def __init__(
        self,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        init_v: Callable[[Character], int],
        set_v: Callable[[Character, int], bool],
        min_value: Callable[[Character], Optional[int]] = lambda _: 0,
        max_value: Callable[[Character], Optional[int]] = lambda _: None,
    ) -> None:
        super().__init__(name, type, subtype)
        self._init_v = init_v
        self._set_v = set_v
        self._min_value = min_value
        self._max_value = max_value

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        if is_first:
            self._init_value = self._init_v(self._ch)
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
        if enforce_costs and self._cur_value < 0:
            raise IllegalMoveException(
                f"You do not have enough {self._name} to do this."
            )
        if is_last:
            self._finish()

    def _finish(self) -> None:
        self._cur_value = clamp(
            self._cur_value,
            min=self._min_value(self._ch),
            max=self._max_value(self._ch),
        )
        if self._cur_value == self._init_value and not self._comments:
            return
        add_record = self._set_v(self._ch, self._cur_value)
        if add_record:
            self._records.append(
                Record.create_detached(
                    entity_uuid=self._ch.uuid,
                    type=self._type,
                    subtype=self._subtype,
                    old_value=self._init_value,
                    new_value=self._cur_value,
                    comments=self._comments,
                )
            )


class SimpleIntField(IntField):
    def __init__(
        self,
        display_name: str,
        field_name: str,
        type: EffectType,
        subtype: Optional[str] = None,
        min_value: Callable[[Character], Optional[int]] = lambda _: 0,
        max_value: Callable[[Character], Optional[int]] = lambda _: None,
    ) -> None:
        if subtype is not None:
            raise Exception(
                f"Subtype should be none for field {field_name}, but is {subtype}"
            )

        init_v = lambda e: getattr(e._data, field_name)

        def set_v(ch: Character, val: int) -> None:
            setattr(ch, field_name, val)
            return True

        super().__init__(
            display_name, type, subtype, init_v, set_v, min_value, max_value
        )


class SimpleDictIntField(IntField):
    def __init__(
        self,
        display_name: str,
        field_name: str,
        type: EffectType,
        subtype: Optional[str],
        min_value: Callable[[Character], Optional[int]] = lambda _: 0,
        max_value: Callable[[Character], Optional[int]] = lambda _: None,
    ) -> None:
        if subtype is None:
            raise Exception(f"Subtype should be non-none for field {field_name}")

        init_v = lambda e: getattr(e._data, field_name).get(subtype, 0)

        def set_v(ch: Character, val: int) -> None:
            d = getattr(ch, field_name)
            d[subtype] = val
            return True

        super().__init__(
            display_name, type, subtype, init_v, set_v, min_value, max_value
        )

    @classmethod
    def make_fields(
        cls,
        split_effects: Dict[Tuple[EffectType, Optional[str]], List[Effect]],
        name_pfx: str,
        field_name: str,
        type: EffectType,
        **kwargs,
    ) -> List[Field]:
        subtypes = [k[1] for k in split_effects if k[0] == type and k[1] is not None]
        return [
            cls(f"{subtype} {name_pfx}", field_name, type, subtype, **kwargs)
            for subtype in subtypes
        ]


def apply_effects(
    effects: List[Effect],
    target: Any,
    fields: List[Callable[[], List[Field]]],
    records: List[Record],
    enforce_costs: bool,
) -> None:
    effects_split = defaultdict(list)
    for effect in effects:
        effects_split[(effect.type, effect.subtype)].append(effect)
    ffs = []
    for field_func in fields:
        for f in field_func(effects_split):
            ffs.append((f._type, f._subtype))
            f.apply_single(target, effects_split, records, enforce_costs)
    if effects_split:
        raise Exception(f"Effects remaining unprocessed ({ffs}): {effects_split}")
