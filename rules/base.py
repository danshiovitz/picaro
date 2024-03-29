from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from .types.internal import Overlay, OverlayType, Trigger, TriggerType


@dataclass
class RulesContext:
    # character this is all running as, not necessarily the currently
    # active entity or anything
    character_name: str
    # cache of all the overlays visible to each entity, sorted by type
    overlays: Dict[str, Dict[Tuple[OverlayType, str], List[Overlay]]] = field(
        default_factory=dict
    )
    in_use_overlays: Set[str] = field(default_factory=set)
    # cache of triggers
    triggers: Dict[str, Dict[Tuple[TriggerType, str], List[Trigger]]] = field(
        default_factory=dict
    )


rules_cache: ContextVar[RulesContext] = ContextVar("rules_cache")


class RulesManager:
    def __init__(self, character_name: str) -> None:
        self.character_name = character_name

    def __enter__(self) -> "RulesManager":
        if rules_cache.get(None) is not None:
            raise Exception(
                "Trying to create a nested rules cache, this is probably bad"
            )
        new_ctx = RulesContext(character_name=self.character_name)
        self.ctx_token = rules_cache.set(new_ctx)
        return self

    def __exit__(self, *exc: Any) -> None:
        rules_cache.reset(self.ctx_token)


def get_rules_cache() -> RulesContext:
    cur = rules_cache.get(None)
    if cur is None:
        raise Exception("No rules context created")
    return cur
