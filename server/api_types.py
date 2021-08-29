from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.job import Job
from picaro.engine.snapshot import Board, Character, Encounter, Hex, Oracle, Project, Token
from picaro.engine.types import (
    Action,
    Choices,
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
    OracleStatus,
    Outcome,
    TaskStatus,
    TaskType,
    TableauCard,
)


@dataclass(frozen=True)
class Player:
    id: int
    name: str


@dataclass(frozen=True)
class SearchProjectsResponse:
    projects: List[Project]


@dataclass(frozen=True)
class StartTaskRequest:
    task_name: str


@dataclass(frozen=True)
class StartTaskResponse:
    outcome: Outcome


@dataclass(frozen=True)
class ReturnTaskRequest:
    task_name: str


@dataclass(frozen=True)
class ReturnTaskResponse:
    outcome: Outcome


@dataclass(frozen=True)
class SearchSkillsResponse:
    skills: List[str]


@dataclass(frozen=True)
class SearchJobsResponse:
    jobs: List[Job]


@dataclass(frozen=True)
class SearchOraclesResponse:
    oracles: List[Oracle]


@dataclass(frozen=True)
class GetOracleCostRequest:
    pass


@dataclass(frozen=True)
class GetOracleCostResponse:
    cost: Choices


@dataclass(frozen=True)
class CreateOracleRequest:
    request: str
    payment_selections: Dict[int, int]


@dataclass(frozen=True)
class CreateOracleResponse:
    id: str
    outcome: Outcome


@dataclass(frozen=True)
class AnswerOracleRequest:
    id: str
    response: str
    proposal: List[Effect]


@dataclass(frozen=True)
class AnswerOracleResponse:
    outcome: Outcome


@dataclass(frozen=True)
class ConfirmOracleRequest:
    id: str
    confirm: bool


@dataclass(frozen=True)
class ConfirmOracleResponse:
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
