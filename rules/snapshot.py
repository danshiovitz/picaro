from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
from enum import Enum, auto as enum_auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.store.common_types import (
    Choices,
    TableauCard,
    Effect,
    EffectType,
    EncounterCheck,
    EntityType,
    Filter,
    FullCard,
    FullCardType,
    JobType,
    OracleStatus,
    Overlay,
    Route,
    RouteType,
    TaskStatus,
    TaskType,
    TemplateCard,
    Trigger,
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
    uuid: str
    entity: str
    location: str


@dataclass(frozen=True)
class Country:
    uuid: str
    name: str
    capitol_hex: str
    resources: Sequence[str]


@dataclass(frozen=True)
class Board:
    hexes: Sequence[Hex]
    countries: Sequence[Country]


@dataclass(frozen=True)
class Action:
    uuid: str
    name: str
    cost: Sequence[Effect]
    benefit: Sequence[Effect]
    is_private: bool
    filters: Sequence[Filter]
    route: Route


@dataclass(frozen=True)
class Gadget:
    uuid: str
    name: str
    entity: str
    overlays: Sequence[Overlay]
    triggers: Sequence[Trigger]
    actions: Sequence[Action]


@dataclass(frozen=True)
class Entity:
    uuid: str
    type: EntityType
    subtype: Optional[str]
    name: str
    gadgets: Sequence[Gadget]
    locations: Sequence[str]


@dataclass(frozen=True)
class Job:
    uuid: str
    name: str
    type: JobType
    rank: int
    promotions: Sequence[str]
    deck_name: str
    base_skills: Sequence[str]
    encounter_distances: Sequence[int]


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
    uuid: str
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
    uuid: str
    name: str
    type: FullCardType
    data: Any
    age: int
    location: str
    route: Route

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[FullCardType, str]) -> type:
        if type(type_val) is str:
            type_val = FullCardType[type_val]

        if type_val == FullCardType.CHALLENGE:
            return Sequence[EncounterCheck]
        elif type_val in (FullCardType.CHOICE, FullCardType.SPECIAL):
            return str
        else:
            raise Exception(f"Unknown encounter type: {type_val.name}")


@dataclass(frozen=True)
class Encounter:
    uuid: str
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
            raise Exception(f"Unexpected encounter type: {type_val.name}")


@dataclass(frozen=True)
class Character:
    uuid: str
    name: str
    player_uuid: str
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
    encounter: Optional[Encounter]
    queued: Sequence[FullCard]
    emblems: Sequence[Gadget]
    tasks: Sequence[Task]


@dataclass(frozen=True)
class TemplateDeck:
    name: str
    cards: Sequence[TemplateCard]


@dataclass(frozen=True)
class Record:
    uuid: str
    entity_uuid: str
    type: EffectType
    subtype: Optional[str]
    old_value: Any
    new_value: Any
    comments: Sequence[str]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EffectType, str]) -> type:
        if type(type_val) is str:
            type_val = EffectType[type_val]

        if type_val == EffectType.ADD_EMBLEM:
            return Gadget
        elif type_val == EffectType.QUEUE_ENCOUNTER:
            return TemplateCard
        elif type_val in (
            EffectType.MODIFY_JOB,
            EffectType.MODIFY_LOCATION,
        ):
            return str
        else:
            return int


@dataclass(frozen=True)
class Game:
    uuid: str
    name: str
    skills: Sequence[str]
    resources: Sequence[str]
    zodiacs: Sequence[str]


@dataclass(frozen=True)
class CreateGameData:
    name: str
    skills: List[str]
    resources: List[str]
    jobs: List[Job]
    template_decks: List[TemplateDeck]
    zodiacs: List[str]
    hexes: List[Hex]
    countries: List[Country]
    entities: List[Entity]


@dataclass(frozen=True)
class EncounterCommands:
    encounter_uuid: str
    adjusts: Sequence[int]
    transfers: Sequence[Tuple[int, int]]
    flee: bool
    luck_spent: int
    rolls: Sequence[int]
    # map of choice index -> times chosen
    choices: Dict[int, int]
