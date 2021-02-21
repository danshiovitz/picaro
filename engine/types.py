from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar


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
    DISRUPT_JOB = enum_auto()
    TRANSPORT = enum_auto()


@dataclass(frozen=True)
class Effect:
    type: EffectType
    value: int
    param: Optional[Any] = None
    is_cost: bool = False


class JobType(Enum):
    LACKEY = enum_auto()
    SOLO = enum_auto()
    CAPTAIN = enum_auto()
    KING = enum_auto()


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    target_number: int
    reward: EncounterEffect
    penalty: EncounterEffect


class ChoiceType(Enum):
    NONE = enum_auto()
    REQUIRED = enum_auto()
    OPTIONAL = enum_auto()
    RANDOM = enum_auto()


@dataclass(frozen=True)
class TemplateCard:
    copies: int
    name: str
    desc: str
    skills: Sequence[str] = ()
    rewards: Sequence[EncounterEffect] = ()
    penalties: Sequence[EncounterEffect] = ()
    choice_type: ChoiceType = ChoiceType.NONE
    choices: Sequence[Sequence[Effect]] = ()


@dataclass(frozen=True)
class FullCard:
    id: str
    name: str
    desc: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
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
    choice: Optional[int]


T = TypeVar("T")


@dataclass(frozen=True)
class EncounterSingleOutcome(Generic[T]):
    new_val: T
    old_val: T
    comments: List[str]


@dataclass(frozen=True)
class EncounterOutcome:
    coins: Optional[EncounterSingleOutcome[int]]
    xp: Dict[str, EncounterSingleOutcome[int]]
    reputation: Optional[EncounterSingleOutcome[int]]
    health: Optional[EncounterSingleOutcome[int]]
    resources: Optional[EncounterSingleOutcome[int]]
    quest: Optional[EncounterSingleOutcome[int]]
    turns: Optional[EncounterSingleOutcome[int]]
    speed: Optional[EncounterSingleOutcome[int]]
    transport_location: Optional[EncounterSingleOutcome[str]]
    new_job: Optional[EncounterSingleOutcome[str]]


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
    INIT_SPEED = enum_auto()


@dataclass(frozen=True)
class Feat:
    hook: HookType
    value: int
    param: Optional[str]


@dataclass(frozen=True)
class Emblem:
    name: str
    feats: List[Feat]


@dataclass(frozen=True)
class Character:
    name: str
    player_id: int
    skills: Dict[str, int]
    skill_xp: Dict[str, int]
    job: str
    health: int
    coins: int
    resources: int
    reputation: int
    quest: int
    location: str
    remaining_turns: int
    luck: int
    speed: int
    tableau: Sequence[TableauCard]
    encounters: Sequence[Encounter]
    emblems: Sequence[Emblem]


@dataclass(frozen=True)
class Game:
    id: int
    name: str
