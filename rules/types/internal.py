from dataclasses import dataclass, replace as dataclasses_replace
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional, Sequence, Set

from picaro.common.hexmap.types import CubeCoordinate
from picaro.common.storage import (
    StorageBase,
    StandardWrapper,
    make_double_uuid,
    get_parent_uuid,
)

from .external import (
    Challenge,
    Choice,
    Choices,
    Effect,
    EffectType,
    EncounterCheck,
    EncounterContextType,
    EntityType,
    Entity as external_Entity,
    Filter,
    FilterType,
    FullCard,
    FullCardType,
    JobType,
    Outcome,
    Overlay,
    OverlayType,
    Route,
    RouteType,
    TemplateCard,
    TemplateCardType,
    Title,
    TriggerType,
)


@dataclass(frozen=True)
class Encounter:
    card: FullCard
    rolls: Sequence[Sequence[int]]


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
    value: int


@dataclass(frozen=True)
class ResourceCard:
    name: str
    type: str
    value: int


class Game(StandardWrapper):
    class Data(StorageBase["Game.Data"]):
        TABLE_NAME = "game"

        uuid: str
        name: str
        skills: List[str]
        resources: List[str]
        zodiacs: List[str]

    @classmethod
    def load(cls) -> "Game":
        return cls._load_helper_single([], {})

    @classmethod
    def load_for_write(cls) -> "Game":
        return cls._load_helper_single([], {}, can_write=True)

    @classmethod
    def load_by_name(cls, name: str) -> "Game":
        return cls._load_helper_single(["name = :name"], {"name": name})


class TemplateDeck(StandardWrapper):
    class Data(StorageBase["TemplateDeck.Data"]):
        TABLE_NAME = "template_deck"

        name: str
        copies: List[int]
        cards: List[TemplateCard]


class Hex(StandardWrapper):
    class Data(StorageBase["Hex.Data"]):
        TABLE_NAME = "hex"

        name: str
        terrain: str
        country: str
        x: int
        y: int
        z: int
        danger: int

    @classmethod
    def load_by_coordinate(cls, cube: CubeCoordinate) -> "Hex":
        return cls._load_helper_single(
            ["x = :x", "y = :y", "z = :z"], {"x": cube.x, "y": cube.y, "z": cube.z}
        )

    @classmethod
    def load_by_distance(
        cls, cube: CubeCoordinate, min_distance: int, max_distance: int
    ) -> List["Hex"]:
        dist_clause = "((abs(:c_x - x) + abs(:c_y - y) + abs(:c_z - z)) / 2) BETWEEN :min_distance AND :max_distance"
        return cls._load_helper(
            [dist_clause],
            {
                "c_x": cube.x,
                "c_y": cube.y,
                "c_z": cube.z,
                "min_distance": min_distance,
                "max_distance": max_distance,
            },
        )


class Token(StandardWrapper):
    class Data(StorageBase["Token.Data"]):
        TABLE_NAME = "token"

        uuid: str
        entity: str
        location: str

    @classmethod
    def load_all_by_entity(cls, entity: str) -> List["Token"]:
        return cls._load_helper(["entity = :entity"], {"entity": entity})

    @classmethod
    def load_single_by_entity(cls, entity: str) -> "Token":
        return cls._load_helper_single(["entity = :entity"], {"entity": entity})

    @classmethod
    def load_single_by_entity_for_write(cls, entity: str) -> "Token":
        return cls._load_helper_single(
            ["entity = :entity"], {"entity": entity}, can_write=True
        )


class Country(StandardWrapper):
    class Data(StorageBase["Country.Data"]):
        TABLE_NAME = "country"
        LOAD_KEY = "name"

        uuid: str
        name: str
        capitol_hex: str
        resources: List[str]


class HexDeck(StandardWrapper):
    class Data(StorageBase["HexDeck.Data"]):
        TABLE_NAME = "hex_deck"

        # Decks are per-hex-type, so deck name is the terrain name
        name: str
        cards: List[TemplateCard]


class ResourceDeck(StandardWrapper):
    class Data(StorageBase["ResourceDeck.Data"]):
        TABLE_NAME = "resource_deck"

        # Decks are per-country, so deck name is the country name
        name: str
        cards: List[ResourceCard]


class Entity(StandardWrapper):
    class Data(StorageBase["Entity.Data"]):
        TABLE_NAME = "entity"

        uuid: str
        type: EntityType
        subtype: Optional[str]
        name: str
        desc: Optional[str] = None

    @classmethod
    def load_by_name(cls, name: str) -> "Entity":
        return cls._load_helper_single(["name = :name"], {"name": name})


class Job(StandardWrapper):
    class Data(StorageBase["Job.Data"]):
        TABLE_NAME = "job"
        LOAD_KEY = "name"

        uuid: str
        name: str
        type: JobType
        rank: int
        promotions: List[str]
        deck_name: str
        base_skills: List[str]
        encounter_distances: List[int]


class Overlay(StandardWrapper):
    class Data(StorageBase["Overlay.Data"]):
        TABLE_NAME = "overlay"

        uuid: str
        name: Optional[str]
        entity_uuid: str
        title: Optional[str]
        type: OverlayType
        subtype: Optional[str]
        is_private: bool
        filters: Sequence[Filter]
        value: int

    @classmethod
    def load_for_entity(cls, entity_uuid: str) -> List["Overlay"]:
        return cls._load_helper(
            ["entity_uuid = :entity_uuid"], {"entity_uuid": entity_uuid}
        )

    @classmethod
    def load_visible_for_entity(cls, entity_uuid: str) -> List["Overlay"]:
        return cls._load_helper(
            ["entity_uuid = :entity_uuid or is_private = 0"],
            {"entity_uuid": entity_uuid},
        )


class Trigger(StandardWrapper):
    class Data(StorageBase["Trigger.Data"]):
        TABLE_NAME = "trigger"

        uuid: str
        name: Optional[str]
        entity_uuid: str
        title: Optional[str]
        type: TriggerType
        subtype: Optional[str]
        is_private: bool
        filters: Sequence[Filter]
        costs: Sequence[Effect]
        effects: Sequence[Effect]

    @classmethod
    def load_for_entity(cls, entity_uuid: str) -> List["Trigger"]:
        return cls._load_helper(
            ["entity_uuid = :entity_uuid"], {"entity_uuid": entity_uuid}
        )

    @classmethod
    def load_visible_for_entity(cls, entity_uuid: str) -> List["Trigger"]:
        return cls._load_helper(
            ["entity_uuid = :entity_uuid or is_private = 0"],
            {"entity_uuid": entity_uuid},
        )


class TurnFlags(Enum):
    ACTED = enum_auto()
    HAD_TRAVEL_ENCOUNTER = enum_auto()
    BAD_REP_CHECKED = enum_auto()
    RAN_END_TURN_TRIGGERS = enum_auto()


class Character(StandardWrapper):
    class Data(StorageBase["Character.Data"]):
        TABLE_NAME = "character"
        SECONDARY_TABLE = True

        uuid: str
        player_uuid: str
        job_name: str
        skill_xp: Dict[str, int]
        health: int
        coins: int
        resources: Dict[str, int]
        reputation: int
        remaining_turns: int
        luck: int
        turn_flags: Set[TurnFlags]
        speed: int
        tableau: List[TableauCard]
        encounter: Optional[Encounter]
        queued: List[FullCard]
        job_deck: List[TemplateCard]
        travel_special_deck: List[TemplateCard]
        camp_deck: List[TemplateCard]

    @classmethod
    def load_by_name(cls, character_name: str) -> "Character":
        # this is going to be so common, let's support it here:
        entity = Entity.load_by_name(character_name)
        return cls.load(entity.uuid)

    @classmethod
    def load_by_name_for_write(cls, character_name: str) -> "Character":
        # this is going to be so common, let's support it here:
        entity = Entity.load_by_name(character_name)
        return cls.load_for_write(entity.uuid)

    def acted_this_turn(self) -> None:
        return TurnFlags.ACTED in self._data.turn_flags

    def check_set_flag(self, flag: TurnFlags) -> bool:
        if not self._write:
            raise Exception(f"Can't set flag on non-writable character")
        prev = flag in self._data.turn_flags
        self._data.turn_flags.add(flag)
        return prev


class Record(StandardWrapper):
    class Data(StorageBase["Record.Data"]):
        TABLE_NAME = "record"

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
            if type_val == EffectType.ADD_ENTITY:
                return external_Entity
            elif type_val == EffectType.ADD_TITLE:
                return Title
            elif type_val == EffectType.QUEUE_ENCOUNTER:
                return Optional[TemplateCard]
            elif type_val in (
                EffectType.MODIFY_JOB,
                EffectType.MODIFY_LOCATION,
            ):
                return str
            else:
                return int
