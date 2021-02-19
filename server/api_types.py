from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.snapshot import Board, Character, Encounter
from picaro.engine.types import (
    ChoiceType,
    TableauCard,
    Effect,
    EffectType,
    Emblem,
    EncounterCheck,
    EncounterActions,
    EncounterOutcome,
    EncounterSingleOutcome,
    Feat,
    Hex,
    HookType,
    Terrains,
    Token,
    TokenTypes,
)


@dataclass(frozen=True)
class Player:
    id: int
    name: str


@dataclass(frozen=True)
class JobRequest:
    card_id: str


@dataclass(frozen=True)
class JobResponse:
    pass


@dataclass(frozen=True)
class CampRequest:
    rest: bool


@dataclass(frozen=True)
class CampResponse:
    pass


@dataclass(frozen=True)
class TravelRequest:
    step: str


@dataclass(frozen=True)
class TravelResponse:
    pass


@dataclass(frozen=True)
class EndTurnRequest:
    pass


@dataclass(frozen=True)
class EndTurnResponse:
    pass


@dataclass(frozen=True)
class ResolveEncounterRequest:
    actions: EncounterActions


@dataclass(frozen=True)
class ResolveEncounterResponse:
    outcome: EncounterOutcome


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
