from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.rules.snapshot import (
    Action,
    Board,
    Character,
    CreateGameData as CreateGameRequest,
    Country,
    Encounter,
    EncounterCommands,
    EncounterType,
    Entity,
    Gadget,
    Game,
    Hex,
    Job,
    Oracle,
    Project,
    Record,
    Route,
    RouteType,
    TemplateDeck,
    Token,
)
from picaro.store.common_types import (
    Choice,
    Choices,
    Effect,
    EffectType,
    EncounterCheck,
    EntityType,
    Filter,
    FilterType,
    FullCardType,
    OracleStatus,
    Outcome,
    Overlay,
    OverlayType,
    ProjectType,
    TaskStatus,
    TaskType,
    TableauCard,
    TemplateCard,
    TemplateCardType,
)


@dataclass(frozen=True)
class Player:
    uuid: str
    name: str


@dataclass(frozen=True)
class SearchGamesResponse:
    games: List[Game]


@dataclass(frozen=True)
class SearchEntitiesResponse:
    entities: List[Entity]


@dataclass(frozen=True)
class SearchProjectsResponse:
    projects: List[Project]


@dataclass(frozen=True)
class StartTaskRequest:
    task_name: str


@dataclass(frozen=True)
class StartTaskResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class ReturnTaskRequest:
    task_name: str


@dataclass(frozen=True)
class ReturnTaskResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class SearchResourcesResponse:
    resources: List[str]


@dataclass(frozen=True)
class SearchSkillsResponse:
    skills: List[str]


@dataclass(frozen=True)
class SearchJobsResponse:
    jobs: List[Job]


@dataclass(frozen=True)
class SearchActionsResponse:
    actions: List[Action]


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
    uuid: str
    records: Sequence[Record]


@dataclass(frozen=True)
class AnswerOracleRequest:
    uuid: str
    response: str
    proposal: List[Effect]


@dataclass(frozen=True)
class AnswerOracleResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class ConfirmOracleRequest:
    uuid: str
    confirm: bool


@dataclass(frozen=True)
class ConfirmOracleResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class JobRequest:
    card_uuid: str


@dataclass(frozen=True)
class JobResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class ActionRequest:
    action_uuid: str


@dataclass(frozen=True)
class ActionResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class CampRequest:
    rest: bool


@dataclass(frozen=True)
class CampResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class TravelRequest:
    step: str


@dataclass(frozen=True)
class TravelResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class EndTurnRequest:
    pass


@dataclass(frozen=True)
class EndTurnResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class ResolveEncounterRequest:
    actions: EncounterCommands


@dataclass(frozen=True)
class ResolveEncounterResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class CreateGameResponse:
    game_id: str


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
