from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.common.serializer import (
    HasAnyType,
    SubclassVariant,
    external_fields_for,
    subclass_of,
)


class Outcome(Enum):
    NOTHING = enum_auto()
    GAIN_COINS = enum_auto()
    GAIN_XP = enum_auto()
    GAIN_REPUTATION = enum_auto()
    GAIN_HEALING = enum_auto()
    GAIN_RESOURCES = enum_auto()
    GAIN_TURNS = enum_auto()
    GAIN_SPEED = enum_auto()
    VICTORY = enum_auto()
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
    ADD_ENTITY = enum_auto()
    ADD_TITLE = enum_auto()
    QUEUE_ENCOUNTER = enum_auto()
    MODIFY_LOCATION = enum_auto()
    MODIFY_JOB = enum_auto()
    TICK_METER = enum_auto()
    # "complex" effects that trigger others
    LEADERSHIP = enum_auto()
    TRANSPORT = enum_auto()


class EntityType(Enum):
    CHARACTER = enum_auto()
    LANDMARK = enum_auto()
    EVENT = enum_auto()


@dataclass(frozen=True)
class Effect(SubclassVariant):
    type: EffectType
    comment: Optional[str] = None


class JobType(Enum):
    LACKEY = enum_auto()
    SOLO = enum_auto()
    CAPTAIN = enum_auto()
    KING = enum_auto()


@dataclass(frozen=True)
class EncounterCheck:
    skill: str
    modifier: Optional[int]
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
class TemplateCard(HasAnyType):
    ANY_TYPE_MAP = {
        TemplateCardType.CHALLENGE: Challenge,
        TemplateCardType.CHOICE: Choices,
        TemplateCardType.SPECIAL: str,
    }

    name: str
    desc: str
    type: TemplateCardType
    data: Any
    annotations: Dict[str, str] = MappingProxyType({})


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
class FullCard(HasAnyType):
    ANY_TYPE_MAP = {
        FullCardType.CHALLENGE: Sequence[EncounterCheck],
        FullCardType.CHOICE: Choices,
        FullCardType.SPECIAL: str,
    }

    uuid: str
    name: str
    desc: str
    type: FullCardType
    data: Any
    signs: Sequence[str]
    annotations: Dict[str, str] = MappingProxyType({})


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


class FilterType(Enum):
    SKILL_GTE = enum_auto()
    NEAR_HEX = enum_auto()
    NEAR_TOKEN = enum_auto()
    IN_COUNTRY = enum_auto()


@dataclass(frozen=True)
class Filter(SubclassVariant):
    type: FilterType
    reverse: bool = False


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
    TRADE_PRICE = enum_auto()


@dataclass(frozen=True)
class Overlay(SubclassVariant):
    uuid: str
    type: OverlayType
    is_private: bool
    filters: Sequence[Filter]


class TriggerType(Enum):
    ACTION = enum_auto()
    ENTER_HEX = enum_auto()
    START_TURN = enum_auto()
    END_TURN = enum_auto()


@dataclass(frozen=True)
class Trigger(SubclassVariant):
    uuid: str
    type: TriggerType
    is_private: bool
    filters: Sequence[Filter]
    effects: Sequence[Effect]


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
class Meter:
    uuid: str
    name: str
    min_value: int
    max_value: int
    cur_value: int
    empty_effects: Sequence[Effect] = ()
    full_effects: Sequence[Effect] = ()


@dataclass(frozen=True)
class Title:
    name: Optional[str]
    overlays: Sequence[Overlay] = ()
    triggers: Sequence[Trigger] = ()
    actions: Sequence[Action] = ()
    meters: Sequence[Meter] = ()


@dataclass(frozen=True)
class Entity:
    uuid: str
    type: EntityType
    subtype: Optional[str]
    name: str
    desc: Optional[str] = None
    titles: Sequence[Title] = ()
    locations: Sequence[str] = ()


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
class TableauCard(HasAnyType):
    ANY_TYPE_MAP = {
        FullCardType.CHALLENGE: Sequence[EncounterCheck],
        FullCardType.CHOICE: str,
        FullCardType.SPECIAL: str,
    }

    uuid: str
    name: str
    type: FullCardType
    data: Any
    age: int
    location: str
    route: Route


@dataclass(frozen=True)
class Encounter(HasAnyType):
    ANY_TYPE_MAP = {
        EncounterType.CHALLENGE: Sequence[EncounterCheck],
        EncounterType.CHOICE: Choices,
    }

    uuid: str
    name: str
    desc: str
    type: EncounterType
    data: Any
    signs: Sequence[str]
    rolls: Sequence[Sequence[int]]


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
    titles: Sequence[Title] = ()


@dataclass(frozen=True)
class TemplateDeck:
    name: str
    copies: Sequence[int]
    cards: Sequence[TemplateCard]


@dataclass(frozen=True)
class Record(SubclassVariant):
    uuid: str
    type: EffectType
    comments: Sequence[str]


@dataclass(frozen=True)
class Game:
    uuid: str
    name: str
    skills: Sequence[str]
    resources: Sequence[str]
    zodiacs: Sequence[str]


@subclass_of(Effect, [])
class AmountEffect(Effect):
    amount: int
    is_absolute: bool = False


@subclass_of(
    Effect,
    [
        EffectType.MODIFY_COINS,
        EffectType.MODIFY_REPUTATION,
        EffectType.MODIFY_HEALTH,
        EffectType.MODIFY_TURNS,
        EffectType.MODIFY_SPEED,
        EffectType.MODIFY_LUCK,
        EffectType.LEADERSHIP,
        EffectType.TRANSPORT,
    ],
)
class EntityAmountEffect(AmountEffect):
    entity_uuid: Optional[str] = None


@subclass_of(Effect, [EffectType.MODIFY_XP])
class SkillAmountEffect(EntityAmountEffect):
    skill: Optional[str]


@subclass_of(Effect, [EffectType.MODIFY_RESOURCES])
class ResourceAmountEffect(EntityAmountEffect):
    resource: Optional[str]


@subclass_of(Effect, [EffectType.TICK_METER])
class MeterAmountEffect(AmountEffect):
    entity_uuid: str
    meter_uuid: str


@subclass_of(Effect, [EffectType.MODIFY_ACTIVITY])
class EnableEffect(Effect):
    enable: bool
    entity_uuid: Optional[str] = None


@subclass_of(Effect, [EffectType.ADD_ENTITY])
class AddEntityEffect(Effect):
    entity: Entity


@subclass_of(Effect, [EffectType.QUEUE_ENCOUNTER])
class EncounterEffect(Effect):
    encounter: TemplateCard
    entity_uuid: Optional[str] = None


@subclass_of(Effect, [EffectType.ADD_TITLE])
class AddTitleEffect(Effect):
    title: Title
    entity_uuid: Optional[str] = None


@subclass_of(Effect, [EffectType.MODIFY_LOCATION])
class LocationEffect(Effect):
    hex: str
    entity_uuid: Optional[str] = None


@subclass_of(Effect, [EffectType.MODIFY_JOB])
class JobEffect(Effect):
    job_name: str
    entity_uuid: Optional[str] = None


@subclass_of(Filter, [FilterType.SKILL_GTE])
class SkillFilter(Filter):
    skill: str
    value: int


@subclass_of(Filter, [FilterType.NEAR_HEX])
class HexFilter(Filter):
    hex: str
    distance: int


@subclass_of(Filter, [FilterType.NEAR_TOKEN])
class TokenFilter(Filter):
    entity_uuid: str
    distance: int


@subclass_of(Filter, [FilterType.IN_COUNTRY])
class CountryFilter(Filter):
    country: str


@subclass_of(
    Overlay,
    [
        OverlayType.INIT_TABLEAU_AGE,
        OverlayType.INIT_TURNS,
        OverlayType.MAX_HEALTH,
        OverlayType.MAX_LUCK,
        OverlayType.MAX_TABLEAU_SIZE,
        OverlayType.INIT_SPEED,
        OverlayType.MAX_RESOURCES,
        OverlayType.INIT_REPUTATION,
    ],
)
class AmountOverlay(Overlay):
    amount: int


@subclass_of(Overlay, [OverlayType.SKILL_RANK, OverlayType.RELIABLE_SKILL])
class SkillAmountOverlay(AmountOverlay):
    skill: str


@subclass_of(Overlay, [OverlayType.TRADE_PRICE])
class ResourceAmountOverlay(AmountOverlay):
    resource: str


@subclass_of(
    Trigger,
    [
        TriggerType.ACTION,
        TriggerType.START_TURN,
        TriggerType.END_TURN,
    ],
)
class StandardTrigger(Trigger):
    # dataclass-construction code doesn't work well if empty subclass
    dummy: int = 0


@subclass_of(Record, [])
class AmountRecord(Record):
    old_amount: int
    new_amount: int


@subclass_of(
    Record,
    [
        EffectType.MODIFY_COINS,
        EffectType.MODIFY_REPUTATION,
        EffectType.MODIFY_HEALTH,
        EffectType.MODIFY_TURNS,
        EffectType.MODIFY_SPEED,
        EffectType.MODIFY_LUCK,
        EffectType.LEADERSHIP,
        EffectType.TRANSPORT,
    ],
)
class EntityAmountRecord(AmountRecord):
    entity_uuid: Optional[str]


@subclass_of(Record, [EffectType.MODIFY_XP])
class SkillAmountRecord(EntityAmountRecord):
    skill: Optional[str]


@subclass_of(Record, [EffectType.MODIFY_RESOURCES])
class ResourceAmountRecord(EntityAmountRecord):
    resource: Optional[str]


@subclass_of(Record, [EffectType.TICK_METER])
class MeterAmountRecord(AmountRecord):
    entity_uuid: str
    meter_uuid: str


@subclass_of(Record, [EffectType.MODIFY_ACTIVITY])
class EnableRecord(Record):
    entity_uuid: str
    enabled: bool


@subclass_of(Record, [EffectType.ADD_ENTITY])
class AddEntityRecord(Record):
    entity: Entity


@subclass_of(Record, [EffectType.QUEUE_ENCOUNTER])
class EncounterRecord(Record):
    entity_uuid: str
    encounter: TemplateCard


@subclass_of(Record, [EffectType.ADD_TITLE])
class AddTitleRecord(Record):
    entity_uuid: str
    title: Title


@subclass_of(Record, [EffectType.MODIFY_LOCATION])
class LocationRecord(Record):
    entity_uuid: str
    old_hex: str
    new_hex: str


@subclass_of(Record, [EffectType.MODIFY_JOB])
class JobRecord(Record):
    entity_uuid: str
    old_job_name: str
    new_job_name: str


@subclass_of(Trigger, [TriggerType.ENTER_HEX])
class HexTrigger(Trigger):
    hex: Optional[str]


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
