import random
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from string import ascii_lowercase
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union

from .base import make_uuid


T = TypeVar("T")


class Outcome(Enum):
    NOTHING = enum_auto()
    GAIN_COINS = enum_auto()
    GAIN_XP = enum_auto()
    GAIN_REPUTATION = enum_auto()
    GAIN_HEALING = enum_auto()
    GAIN_RESOURCES = enum_auto()
    GAIN_TURNS = enum_auto()
    GAIN_PROJECT_XP = enum_auto()
    GAIN_SPEED = enum_auto()
    LOSE_COINS = enum_auto()
    LOSE_REPUTATION = enum_auto()
    DAMAGE = enum_auto()
    LOSE_RESOURCES = enum_auto()
    LOSE_LEADERSHIP = enum_auto()
    TRANSPORT = enum_auto()
    LOSE_TURNS = enum_auto()
    LOSE_SPEED = enum_auto()


class EffectType(Enum):
    MODIFY_COINS = enum_auto()
    MODIFY_XP = enum_auto()
    MODIFY_REPUTATION = enum_auto()
    MODIFY_HEALTH = enum_auto()
    MODIFY_RESOURCES = enum_auto()
    MODIFY_TURNS = enum_auto()
    MODIFY_SPEED = enum_auto()
    MODIFY_ACTIVITY = enum_auto()
    MODIFY_LUCK = enum_auto()
    ADD_EMBLEM = enum_auto()
    QUEUE_ENCOUNTER = enum_auto()
    MODIFY_LOCATION = enum_auto()
    MODIFY_JOB = enum_auto()
    # "complex" effects that trigger others
    LEADERSHIP = enum_auto()
    TRANSPORT = enum_auto()


class EntityType(Enum):
    CHARACTER = enum_auto()
    LANDMARK = enum_auto()


@dataclass(frozen=True)
class Effect(Generic[T]):
    type: EffectType
    value: Optional[Any]
    is_absolute: bool = False
    subtype: Optional[str] = None
    comment: Optional[str] = None
    # if the entity isn't provided, it defaults to "the current character"
    entity_uuid: Optional[str] = None

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
        elif type_val in (EffectType.MODIFY_LOCATION, EffectType.MODIFY_JOB):
            return str
        else:
            return int


class JobType(Enum):
    LACKEY = enum_auto()
    SOLO = enum_auto()
    CAPTAIN = enum_auto()
    KING = enum_auto()


class FilterType(Enum):
    SKILL_GTE = enum_auto()
    NEAR_HEX = enum_auto()
    IN_COUNTRY = enum_auto()
    NOT_IN_COUNTRY = enum_auto()


@dataclass(frozen=True)
class Filter:
    type: FilterType
    subtype: Optional[str]
    value: Optional[int]


class OverlayType(Enum):
    INIT_TABLEAU_AGE = enum_auto()
    INIT_TURNS = enum_auto()
    MAX_HEALTH = enum_auto()
    MAX_LUCK = enum_auto()
    MAX_TABLEAU_SIZE = enum_auto()
    SKILL_RANK = enum_auto()
    RELIABLE_SKILL = enum_auto()
    INIT_SPEED = enum_auto()
    MAX_RESOURCES = enum_auto()
    INIT_REPUTATION = enum_auto()


@dataclass(frozen=True)
class Overlay:
    uuid: str
    type: OverlayType
    value: int
    subtype: Optional[str]
    is_private: bool
    filters: Sequence[Filter]


class TriggerType(Enum):
    MOVE_HEX = enum_auto()
    TURN_BEGIN = enum_auto()
    TURN_END = enum_auto()


@dataclass(frozen=True)
class Trigger:
    uuid: str
    type: TriggerType
    effects: List[Effect]
    subtype: Optional[str]
    is_private: bool
    filters: Sequence[Filter]


@dataclass(frozen=True)
class Action:
    uuid: str
    name: str
    cost: Sequence[Effect]
    benefit: Sequence[Effect]
    is_private: bool
    filters: Sequence[Filter]


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: Outcome
    penalty: Outcome


@dataclass(frozen=True)
class Choice:
    name: Optional[str] = None
    # this is the min/max times this particular choice can be selected
    min_choices: int = 0
    max_choices: int = 1
    # this cost and benefit apply once per time the choice is selected
    cost: Sequence[Effect] = ()
    benefit: Sequence[Effect] = ()


@dataclass(frozen=True)
class Challenge:
    skills: Sequence[str]
    rewards: Sequence[Outcome]
    penalties: Sequence[Outcome]
    difficulty: Optional[int] = None


@dataclass(frozen=True)
class Choices:
    # this is the min/max overall selection count
    min_choices: int
    max_choices: int
    is_random: bool
    choice_list: Sequence[Choice]
    # this cost and benefit apply (once) if you make any selections at all
    cost: Sequence[Effect] = ()
    benefit: Sequence[Effect] = ()


class TemplateCardType(Enum):
    CHALLENGE = enum_auto()
    CHOICE = enum_auto()
    SPECIAL = enum_auto()


@dataclass(frozen=True)
class TemplateCard:
    copies: int
    name: str
    desc: str
    type: TemplateCardType
    data: Any
    unsigned: bool = False
    entity_type: Optional[EntityType] = None
    entity_name: Optional[str] = None

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[TemplateCardType, str]) -> type:
        if type(type_val) is str:
            type_val = TemplateCardType[type_val]

        if type_val == TemplateCardType.CHALLENGE:
            return Challenge
        elif type_val == TemplateCardType.CHOICE:
            return Choices
        else:
            return str


class FullCardType(Enum):
    CHALLENGE = enum_auto()
    CHOICE = enum_auto()
    SPECIAL = enum_auto()


class EncounterContextType(Enum):
    JOB = enum_auto()
    TRAVEL = enum_auto()
    CAMP = enum_auto()
    ACTION = enum_auto()
    SYSTEM = enum_auto()


@dataclass(frozen=True)
class FullCard:
    uuid: str
    name: str
    desc: str
    type: FullCardType
    data: Any
    signs: Sequence[str]
    context_type: EncounterContextType
    entity_type: Optional[EntityType] = None
    entity_name: Optional[str] = None

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[FullCardType, str]) -> type:
        if type(type_val) is str:
            type_val = FullCardType[type_val]

        if type_val == FullCardType.CHALLENGE:
            return Sequence[EncounterCheck]
        elif type_val == FullCardType.CHOICE:
            return Choices
        elif type_val == FullCardType.SPECIAL:
            return str
        else:
            raise Exception(f"Unknown full card type: {type_val.name}")


@dataclass(frozen=True)
class TableauCard:
    card: FullCard
    age: int
    location: str


class TravelCardType(Enum):
    NOTHING = enum_auto()
    DANGER = enum_auto()
    SPECIAL = enum_auto()


@dataclass(frozen=True)
class TravelCard:
    type: TravelCardType
    value: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[TravelCardType, str]) -> type:
        if type(type_val) is str:
            type_val = TravelCardType[type_val]

        if type_val == TravelCardType.SPECIAL:
            return TemplateCard
        else:
            return int


@dataclass(frozen=True)
class Encounter:
    card: FullCard
    rolls: Sequence[int]


@dataclass(frozen=True)
class ResourceCard:
    name: str
    type: str
    value: int


@dataclass(frozen=True)
class ProjectType:
    name: str
    desc: str
    skills: List[str]
    resources: List[str]


class TaskType(Enum):
    CHALLENGE = enum_auto()
    RESOURCE = enum_auto()
    WAITING = enum_auto()
    DISCOVERY = enum_auto()


class TaskStatus(Enum):
    UNASSIGNED = enum_auto()
    IN_PROGRESS = enum_auto()
    FINISHED = enum_auto()


class ProjectStatus(Enum):
    IN_PROGRESS = enum_auto()
    FINISHED = enum_auto()


class OracleStatus(Enum):
    WAITING = enum_auto()
    ANSWERED = enum_auto()
    CONFIRMED = enum_auto()
    REJECTED = enum_auto()


class RouteType(Enum):
    NORMAL = enum_auto()
    GLOBAL = enum_auto()
    UNAVAILABLE = enum_auto()


@dataclass(frozen=True)
class Route:
    type: RouteType
    steps: Sequence[str]
