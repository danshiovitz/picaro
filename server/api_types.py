from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.rules.types.external import *

CreateGameRequest = CreateGameData


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
class SearchHexesResponse:
    hexes: List[Hex]


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
    commands: EncounterCommands


@dataclass(frozen=True)
class ResolveEncounterResponse:
    records: Sequence[Record]


@dataclass(frozen=True)
class CreateGameResponse:
    game_id: str


@dataclass(frozen=True)
class AddCharacterRequest:
    job_name: str
    location: Optional[str]


@dataclass(frozen=True)
class AddCharacterResponse:
    entity_id: str


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
