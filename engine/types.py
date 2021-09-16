import random
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from string import ascii_lowercase
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union


Terrains = [
    "Forest",
    "Jungle",
    "Hills",
    "Mountains",
    "Plains",
    "Desert",
    "Water",
    "City",
    "Swamp",
    "Coastal",
    "Arctic",
]


T = TypeVar("T")


def make_id() -> str:
    return "".join(random.choice(ascii_lowercase) for _ in range(12))


class EncounterEffect(Enum):
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
    ADD_EMBLEM = enum_auto()
    QUEUE_ENCOUNTER = enum_auto()
    MODIFY_LOCATION = enum_auto()
    MODIFY_JOB = enum_auto()
    # effects mostly for projects
    TIME_PASSES = enum_auto()
    EXPLORE = enum_auto()
    # "complex" effects that trigger others
    LEADERSHIP = enum_auto()
    TRANSPORT = enum_auto()
    # display-only effects (at least for now)
    START_TASK = enum_auto()
    RETURN_TASK = enum_auto()


class EntityType(Enum):
    HEX = enum_auto()
    CHARACTER = enum_auto()
    PROJECT = enum_auto()
    TASK = enum_auto()
    CITY = enum_auto()
    MINE = enum_auto()


@dataclass(frozen=True)
class Effect(Generic[T]):
    type: EffectType
    value: Optional[Any]
    is_absolute: bool = False
    subtype: Optional[str] = None
    comment: Optional[str] = None
    # if the entity isn't provided, it defaults to "the current character"
    entity_type: Optional[EntityType] = None
    entity_name: Optional[str] = None

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


@dataclass(frozen=True)
class Job:
    name: str
    type: JobType
    rank: int
    promotions: Sequence[str]
    deck_name: str
    encounter_distances: Sequence[int]


class RuleType(Enum):
    INIT_TABLEAU_AGE = enum_auto()
    INIT_TURNS = enum_auto()
    MAX_HEALTH = enum_auto()
    MAX_LUCK = enum_auto()
    MAX_TABLEAU_SIZE = enum_auto()
    SKILL_RANK = enum_auto()
    RELIABLE_SKILL = enum_auto()
    INIT_SPEED = enum_auto()
    MAX_RESOURCES = enum_auto()


@dataclass(frozen=True)
class Rule:
    type: RuleType
    value: int
    subtype: Optional[str]


class TriggerType(Enum):
    MOVE_HEX = enum_auto()
    TURN_BEGIN = enum_auto()
    TURN_END = enum_auto()


@dataclass(frozen=True)
class Trigger:
    type: TriggerType
    effects: List[Effect]
    subtype: Optional[str]


@dataclass(frozen=True)
class Gadget:
    name: str
    desc: Optional[str]
    rules: Sequence[Rule] = ()
    triggers: Sequence[Trigger] = ()


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EncounterEffect
    penalty: EncounterEffect


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
    rewards: Sequence[EncounterEffect]
    penalties: Sequence[EncounterEffect]
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


@dataclass(frozen=True)
class TemplateDeck:
    name: str
    templates: Sequence[TemplateCard]
    base_skills: Sequence[str]


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
    id: str
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
    is_extra: bool = False  # don't count against limit of tableau size


class AvailabilityType(Enum):
    HEX = enum_auto()
    COUNTRY = enum_auto()
    NOT_COUNTRY = enum_auto()
    GLOBAL = enum_auto()


@dataclass(frozen=True)
class Availability:
    type: AvailabilityType
    location: str
    distance: int


@dataclass(frozen=True)
class Action:
    name: str
    cost: Sequence[Effect] = ()
    benefit: Sequence[Effect] = ()


@dataclass(frozen=True)
class Encounter:
    card: FullCard
    rolls: Sequence[int]


@dataclass(frozen=True)
class EncounterActions:
    adjusts: Sequence[int]
    transfers: Sequence[Tuple[int, int]]
    flee: bool
    luck: int
    rolls: Sequence[int]
    # map of choice index -> times chosen
    choices: Dict[int, int]


@dataclass(frozen=True)
class ResourceCard:
    name: str
    type: str
    value: int


@dataclass(frozen=True)
class Country:
    name: str
    capitol_hex: str
    resources: Sequence[str]


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


@dataclass(frozen=True)
class Record(Generic[T]):
    id: str
    entity_type: EntityType
    entity_name: str
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
            return Optional[TemplateCard]
        elif type_val in (
            EffectType.MODIFY_JOB,
            EffectType.MODIFY_LOCATION,
            EffectType.EXPLORE,
            EffectType.START_TASK,
            EffectType.RETURN_TASK,
        ):
            return str
        else:
            return int

    @classmethod
    def for_token(
        cls,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        old: T,
        new: T,
        comments: List[str],
    ) -> "Record":
        return Record[T](
            make_id(),
            EntityType.TOKEN,
            name,
            type,
            subtype,
            old,
            new,
            tuple(comments),
        )

    @classmethod
    def for_character(
        cls,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        old: T,
        new: T,
        comments: List[str],
    ) -> "Record":
        return Record[T](
            make_id(), EntityType.CHARACTER, name, type, subtype, old, new, comments
        )

    @classmethod
    def for_project(
        cls,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        old: T,
        new: T,
        comments: List[str],
    ) -> "Record":
        return Record[T](
            make_id(), EntityType.PROJECT, name, type, subtype, old, new, comments
        )

    @classmethod
    def for_task(
        cls,
        name: str,
        type: EffectType,
        subtype: Optional[str],
        old: T,
        new: T,
        comments: List[str],
    ) -> "Record":
        return Record[T](
            make_id(),
            EntityType.TASK,
            name,
            type,
            subtype,
            old,
            new,
            comments,
        )


@dataclass(frozen=True)
class Outcome:
    records: Sequence[Record]


@dataclass(frozen=True)
class Game:
    id: int
    name: str
    skills: List[str]
    resources: List[str]
    project_types: List[ProjectType]
    zodiacs: List[str]
