from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.types import (
    Action,
    Choices,
    Country,
    TableauCard,
    Effect,
    EncounterCheck,
    EntityType,
    Gadget,
    Job,
    OracleStatus,
    TaskStatus,
    TaskType,
    TemplateDeck,
    ProjectStatus,
    ProjectType,
)


@dataclass(frozen=True)
class Hex:
    name: str
    coordinate: OffsetCoordinate
    terrain: str
    country: str
    danger: int


@dataclass(frozen=True)
class Token:
    name: str
    type: EntityType
    location: str
    actions: Sequence[Action]
    route: Sequence[str]


@dataclass(frozen=True)
class Board:
    hexes: Sequence[Hex]
    tokens: Sequence[Token]
    resources: Sequence[str]


@dataclass()
class Task:
    name: str
    project_name: str
    task_idx: int
    desc: Optional[str]
    type: TaskType
    cost: List[Effect]
    difficulty: int
    participants: List[str]
    status: TaskStatus
    xp: int
    max_xp: int
    extra: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[TaskType, str]) -> type:
        if type(type_val) is str:
            type_val = TaskType[type_val]

        if type_val == TaskType.CHALLENGE:
            return TaskExtraChallenge
        elif type_val == TaskType.RESOURCE:
            return TaskExtraResource
        elif type_val == TaskType.WAITING:
            return TaskExtraWaiting
        elif type_val == TaskType.DISCOVERY:
            return TaskExtraDiscovery
        else:
            raise Exception("Unknown type")


@dataclass(frozen=True)
class TaskExtraChallenge:
    skills: List[str]


@dataclass(frozen=True)
class TaskExtraResource:
    wanted_resources: Set[str]
    given_resources: Dict[str, int]


@dataclass(frozen=True)
class TaskExtraWaiting:
    turns_waited: int


@dataclass(frozen=True)
class TaskExtraDiscovery:
    ref_hexes: List[Tuple[str, int]]
    possible_hexes: Set[str]
    explored_hexes: Set[str]


@dataclass(frozen=True)
class Project:
    name: str
    desc: str
    type: str
    status: ProjectStatus
    target_hex: str
    tasks: List[Task]


@dataclass(frozen=True)
class Oracle:
    id: str
    status: OracleStatus
    signs: Sequence[str]
    petitioner: str
    payment: Sequence[Effect]
    request: str
    granter: Optional[str]
    response: Optional[str]
    proposal: Optional[List[Effect]]


class EncounterType(Enum):
    CHALLENGE = enum_auto()
    CHOICE = enum_auto()


@dataclass(frozen=True)
class TableauCard:
    id: str
    name: str
    type: EncounterType
    data: Any
    age: int
    location: str
    route: Sequence[str]
    is_extra: bool

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EncounterType, str]) -> type:
        if type(type_val) is str:
            type_val = EncounterType[type_val]

        if type_val == EncounterType.CHALLENGE:
            return Sequence[EncounterCheck]
        elif type_val == EncounterType.CHOICE:
            return Choices
        else:
            raise Exception(f"Unknown encounter type: {type_val.name}")


@dataclass(frozen=True)
class Encounter:
    name: str
    desc: str
    type: EncounterType
    data: Any
    signs: Sequence[str]
    rolls: Sequence[int]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EncounterType, str]) -> type:
        if type(type_val) is str:
            type_val = EncounterType[type_val]

        if type_val == EncounterType.CHALLENGE:
            return Sequence[EncounterCheck]
        elif type_val == EncounterType.CHOICE:
            return Choices
        else:
            raise Exception(f"Unknown encounter type: {type_val.name}")


@dataclass(frozen=True)
class Character:
    name: str
    player_id: int
    skills: Dict[str, int]
    skill_xp: Dict[str, int]
    job: str
    health: int
    max_health: int
    coins: int
    resources: Dict[str, int]
    max_resources: int
    reputation: int
    location: str
    remaining_turns: int
    acted_this_turn: bool
    luck: int
    speed: int
    max_speed: int
    tableau: Sequence[TableauCard]
    encounters: Sequence[Encounter]
    emblems: Sequence[Gadget]
    tasks: Sequence[Task]


@dataclass(frozen=True)
class CreateGameData:
    name: str
    skills: List[str]
    resources: List[str]
    jobs: List[Job]
    template_decks: List[TemplateDeck]
    project_types: List[ProjectType]
    zodiacs: List[str]
    hexes: List[Hex]
    tokens: List[Token]
    countries: List[Country]
