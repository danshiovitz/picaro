from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.snapshot import Board, Character, Encounter, Hex, Project, Token
from picaro.engine.types import (
    Action,
    TableauCard,
    Effect,
    EffectType,
    Emblem,
    EncounterActions,
    EncounterCheck,
    EncounterEffect,
    EntityType,
    Event,
    Feat,
    HookType,
    Outcome,
    ProjectStageStatus,
    ProjectStageType,
)


@dataclass(frozen=True)
class Player:
    id: int
    name: str


@dataclass(frozen=True)
class SearchProjectsResponse:
    projects: List[Project]


@dataclass(frozen=True)
class StartProjectStageRequest:
    project_name: str
    stage_num: int


@dataclass(frozen=True)
class StartProjectStageResponse:
    outcome: Outcome


@dataclass(frozen=True)
class JobRequest:
    card_id: str


@dataclass(frozen=True)
class JobResponse:
    outcome: Outcome


@dataclass(frozen=True)
class TokenActionRequest:
    token: str
    action: str


@dataclass(frozen=True)
class TokenActionResponse:
    outcome: Outcome


@dataclass(frozen=True)
class CampRequest:
    rest: bool


@dataclass(frozen=True)
class CampResponse:
    outcome: Outcome


@dataclass(frozen=True)
class TravelRequest:
    step: str


@dataclass(frozen=True)
class TravelResponse:
    outcome: Outcome


@dataclass(frozen=True)
class EndTurnRequest:
    pass


@dataclass(frozen=True)
class EndTurnResponse:
    outcome: Outcome


@dataclass(frozen=True)
class ResolveEncounterRequest:
    actions: EncounterActions


@dataclass(frozen=True)
class ResolveEncounterResponse:
    outcome: Outcome


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
