from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate


class Outcome(Enum):
    NOTHING = enum_auto()
    GAIN_COINS = enum_auto()
    GAIN_XP = enum_auto()
    GAIN_REPUTATION = enum_auto()
    GAIN_HEALING = enum_auto()
    GAIN_RESOURCES = enum_auto()
    GAIN_TURNS = enum_auto()
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
class Effect:
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
    def any_type(cls, type_val: EffectType) -> type:
        # TODO: figure out how to do this better
        from .snapshot import Gadget as snapshot_Gadget

        if type_val == EffectType.ADD_EMBLEM:
            return snapshot_Gadget
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
    # this costs and effects apply once per time the choice is selected
    costs: Sequence[Effect] = ()
    effects: Sequence[Effect] = ()


@dataclass(frozen=True)
class Challenge:
    skills: Sequence[str]
    rewards: Sequence[Outcome]
    penalties: Sequence[Outcome]


@dataclass(frozen=True)
class Choices:
    # this is the min/max overall selection count
    min_choices: int
    max_choices: int
    choice_list: Sequence[Choice]
    # this costs and effects apply (once) if you make any selections at all
    costs: Sequence[Effect] = ()
    effects: Sequence[Effect] = ()


class TemplateCardType(Enum):
    CHALLENGE = enum_auto()
    CHOICE = enum_auto()
    SPECIAL = enum_auto()


@dataclass(frozen=True)
class TemplateCard:
    name: str
    desc: str
    type: TemplateCardType
    data: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: TemplateCardType) -> type:
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


@dataclass(frozen=True)
class FullCard:
    uuid: str
    name: str
    desc: str
    type: FullCardType
    data: Any
    signs: Sequence[str]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: FullCardType) -> type:
        if type_val == FullCardType.CHALLENGE:
            return Sequence[EncounterCheck]
        elif type_val == FullCardType.CHOICE:
            return Choices
        elif type_val == FullCardType.SPECIAL:
            return str
        else:
            raise Exception(f"Unknown full card type: {type_val.name}")


class RouteType(Enum):
    NORMAL = enum_auto()
    GLOBAL = enum_auto()
    UNAVAILABLE = enum_auto()


@dataclass(frozen=True)
class Route:
    type: RouteType
    steps: Sequence[str]


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
class Action:
    uuid: str
    name: str
    costs: Sequence[Effect]
    effects: Sequence[Effect]
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