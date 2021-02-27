from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .exceptions import BadStateException, IllegalMoveException
from .types import Effect, EffectType, EncounterContextType, EncounterSingleOutcome


class UpdateHolder:
    def __init__(
        self,
        name: str,
        effect_type: EffectType,
        param: Optional[str],
        context_type: EncounterContextType,
        min_val: Optional[int],
        max_val: Optional[int],
        get_f: Callable[[], int],
        set_f: Callable[[int], None],
    ) -> None:
        self._name = name
        self._effect_type = effect_type
        self._param = param
        self._context_type = context_type
        self._min_val = min_val
        self._max_val = max_val
        self._set_f = set_f
        self._init_value = get_f()
        self._cur_value = self._init_value
        self._comments: List[str] = []

    def apply_effects(self, effects: List[Effect]) -> None:
        # bump costs to the front of the list
        effects = sorted(
            effects,
            key=lambda e: (e.type.name, e.param, 0 if e.is_cost else 1, e.value),
        )

        for effect in effects:
            if effect.type != self._effect_type or effect.param != self._param:
                continue
            self.add(effect.value, is_cost=effect.is_cost)

    def add(self, value: int, msg: Optional[str] = None, is_cost: bool = False) -> None:
        self._cur_value += value
        if self._cur_value < 0 and is_cost:
            raise IllegalMoveException(
                f"You do not have enough {self._name} to do this."
            )
        self._comments.append(msg or f"{value:+}")

    def reset(self) -> None:
        self._cur_value = self._init_value
        self._comments = []

    def set_to(self, value: int, msg: str) -> None:
        self.reset()
        self._cur_value = value
        self._comments.append(msg)

    def get_cur_value(self) -> int:
        return self._cur_value

    def to_outcome(self) -> Optional[EncounterSingleOutcome[int]]:
        if self._min_val is not None and self._cur_value < self._min_val:
            self._cur_value = self._min_val
        if self._max_val is not None and self._cur_value > self._max_val:
            self._cur_value = self._max_val
        if self._cur_value == self._init_value and not self._comments:
            return None
        self._set_f(self._cur_value)
        return EncounterSingleOutcome[int](
            old_val=self._init_value, new_val=self._cur_value, comments=self._comments
        )
