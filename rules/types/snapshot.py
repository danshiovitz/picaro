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
)

from picaro.common.hexmap.types import OffsetCoordinate

from .common import (
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
    Overlay,
    Route,
    RouteType,
    TemplateCard,
    Trigger,
)


@dataclass(frozen=True)
class Hex:
    name: str
    coordinate: OffsetCoordinate
    terrain: str
    country: str
    danger: int


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
    desc: Optional[str]
    overlays: Sequence[Overlay]
    triggers: Sequence[Trigger]
    actions: Sequence[Action]
    entity: str


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
    def any_type(cls, type_val: FullCardType) -> type:
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
    rolls: Sequence[Sequence[int]]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: EncounterType) -> type:
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


@dataclass(frozen=True)
class TemplateDeck:
    name: str
    copies: Sequence[int]
    cards: Sequence[TemplateCard]


@dataclass(frozen=True)
class Record:
    uuid: str
    entity_uuid: str
    type: EffectType
    subtype: Optional[str]
    old_value: Optional[Any]
    new_value: Optional[Any]
    comments: Sequence[str]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: EffectType) -> type:
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
