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


class EncounterEffect(Enum):
    NOTHING = enum_auto()
    GAIN_COINS = enum_auto()
    GAIN_XP = enum_auto()
    GAIN_REPUTATION = enum_auto()
    GAIN_HEALING = enum_auto()
    GAIN_RESOURCES = enum_auto()
    GAIN_QUEST = enum_auto()
    GAIN_TURNS = enum_auto()
    LOSE_COINS = enum_auto()
    LOSE_REPUTATION = enum_auto()
    DAMAGE = enum_auto()
    LOSE_RESOURCES = enum_auto()
    DISRUPT_JOB = enum_auto()
    TRANSPORT = enum_auto()
    LOSE_TURNS = enum_auto()
    LOSE_SPEED = enum_auto()


class EffectType(Enum):
    MODIFY_COINS = enum_auto()
    MODIFY_XP = enum_auto()
    MODIFY_REPUTATION = enum_auto()
    MODIFY_HEALTH = enum_auto()
    MODIFY_RESOURCES = enum_auto()
    MODIFY_QUEST = enum_auto()
    MODIFY_TURNS = enum_auto()
    MODIFY_SPEED = enum_auto()
    MODIFY_ACTION = enum_auto()
    ADD_EMBLEM = enum_auto()
    MODIFY_LOCATION = enum_auto()
    MODIFY_JOB = enum_auto()
    # "complex" effects that trigger others
    DISRUPT_JOB = enum_auto()
    TRANSPORT = enum_auto()


@dataclass(frozen=True)
class Effect(Generic[T]):
    type: EffectType
    value: Optional[Any]
    subtype: Optional[str] = None
    is_cost: bool = False

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EffectType, str]) -> type:
        if type(type_val) is str:
            type_val = EffectType[type_val]

        if type_val == EffectType.ADD_EMBLEM:
            return Emblem
        else:
            return int


class JobType(Enum):
    LACKEY = enum_auto()
    SOLO = enum_auto()
    CAPTAIN = enum_auto()
    KING = enum_auto()


@dataclass(frozen=True)
class Action:
    name: str
    cost: List[Effect]
    benefit: List[Effect]


class HookType(Enum):
    INIT_CARD_AGE = enum_auto()
    INIT_TURNS = enum_auto()
    MAX_HEALTH = enum_auto()
    MAX_LUCK = enum_auto()
    MAX_TABLEAU_SIZE = enum_auto()
    SKILL_RANK = enum_auto()
    RELIABLE_SKILL = enum_auto()
    INIT_SPEED = enum_auto()
    MAX_RESOURCES = enum_auto()


@dataclass(frozen=True)
class Feat:
    hook: HookType
    value: int
    subtype: Optional[str]


@dataclass(frozen=True)
class Emblem:
    name: str
    feats: List[Feat]


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EncounterEffect
    penalty: EncounterEffect


@dataclass(frozen=True)
class Choices:
    min_choices: int
    max_choices: int
    is_random: bool
    choice_list: Sequence[Sequence[Effect]]


@dataclass(frozen=True)
class TemplateCard:
    copies: int
    name: str
    desc: str
    skills: Sequence[str] = ()
    rewards: Sequence[EncounterEffect] = ()
    penalties: Sequence[EncounterEffect] = ()
    choices: Optional[Choices] = None
    unsigned: bool = False


@dataclass(frozen=True)
class FullCard:
    id: str
    name: str
    desc: str
    checks: Sequence[EncounterCheck]
    choices: Optional[Choices]
    signs: Sequence[str]


@dataclass(frozen=True)
class TableauCard:
    card: FullCard
    age: int
    location: str


class EncounterContextType(Enum):
    JOB = enum_auto()
    TRAVEL = enum_auto()
    CAMP = enum_auto()
    ACTION = enum_auto()
    SYSTEM = enum_auto()


@dataclass(frozen=True)
class Encounter:
    card: FullCard
    rolls: Sequence[int]
    context_type: EncounterContextType


@dataclass(frozen=True)
class EncounterActions:
    adjusts: Sequence[int]
    transfers: Sequence[Tuple[int, int]]
    flee: bool
    luck: int
    rolls: Sequence[int]
    choices: Sequence[int]


@dataclass(frozen=True)
class Game:
    id: int
    name: str


@dataclass(frozen=True)
class ResourceCard:
    name: str
    type: str
    value: int


@dataclass(frozen=True)
class Country:
    name: str
    capitol_hex: str
    resources: List[str]


class EntityType(Enum):
    HEX = enum_auto()
    TOKEN = enum_auto()
    CHARACTER = enum_auto()


@dataclass(frozen=True)
class Values(Generic[T]):
    old: T
    new: T


@dataclass(frozen=True)
class Event(Generic[T]):
    id: int
    entity_type: EntityType
    entity_name: str
    type: EffectType
    subtype: Optional[str]
    old_value: Any
    new_value: Any
    comments: List[str]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[EffectType, str]) -> type:
        if type(type_val) is str:
            type_val = EffectType[type_val]

        if type_val == EffectType.ADD_EMBLEM:
            return Emblem
        elif type_val in (EffectType.MODIFY_JOB, EffectType.MODIFY_LOCATION):
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
    ) -> "Event":
        return Event[T](
            cls.make_id(), EntityType.TOKEN, name, type, subtype, old, new, comments
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
    ) -> "Event":
        return Event[T](
            cls.make_id(), EntityType.CHARACTER, name, type, subtype, old, new, comments
        )

    @classmethod
    def make_id(cls) -> str:
        return "".join(random.choice(ascii_lowercase) for _ in range(12))


@dataclass(frozen=True)
class Outcome:
    events: List[Event]
