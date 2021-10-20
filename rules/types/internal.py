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
    Filter,
    FilterType,
    FullCard,
    FullCardType,
    Gadget as external_Gadget,
    JobType,
    Outcome,
    Overlay,
    OverlayType,
    Route,
    RouteType,
    TemplateCard,
    TemplateCardType,
    Trigger,
    TriggerType,
)


@dataclass(frozen=True)
class Action:
    uuid: str
    name: str
    costs: Sequence[Effect]
    effects: Sequence[Effect]
    is_private: bool
    filters: Sequence[Filter]


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
    value: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: TravelCardType) -> type:
        if type_val == TravelCardType.SPECIAL:
            return TemplateCard
        else:
            return int


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


class Gadget(StandardWrapper):
    class Data(StorageBase["Gadget.Data"]):
        TABLE_NAME = "gadget"

        uuid: str
        name: str
        desc: Optional[str]
        overlays: List[Overlay]
        triggers: List[Trigger]
        actions: List[Action]
        entity: str

    @classmethod
    def load_for_entity(cls, entity: str) -> List["Gadget"]:
        return [g for g in cls.load_all() if g.entity == entity]

    @classmethod
    def load_action_by_uuid(cls, uuid: str) -> "Action":
        gadget_uuid = get_parent_uuid(uuid)
        gadget = cls.load(gadget_uuid)
        actions = [a for a in gadget.actions if a.uuid == uuid]
        if not actions:
            raise IllegalMoveException(f"No such action: {uuid}")
        return actions[0]

    def add_overlay(
        self,
        type: OverlayType,
        value: int,
        subtype: Optional[str],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add overlay to non-writable gadget")
        self.overlays.append(
            Overlay(
                uuid=make_double_uuid(self.uuid),
                value=value,
                type=type,
                subtype=subtype,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_overlay_object(self, overlay: Overlay) -> None:
        if not self._write:
            raise Exception(f"Can't add overlay to non-writable gadget")
        overlay = dataclasses_replace(overlay, uuid=make_double_uuid(self.uuid))
        self.overlays.append(overlay)

    def add_trigger(
        self,
        type: TriggerType,
        effects: Sequence[Effect],
        subtype: Optional[str],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add trigger to non-writable gadget")
        self.triggers.append(
            Trigger(
                uuid=make_double_uuid(self.uuid),
                effects=effects,
                type=type,
                subtype=subtype,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_trigger_object(self, trigger: Trigger) -> None:
        if not self._write:
            raise Exception(f"Can't add trigger to non-writable gadget")
        trigger = dataclasses_replace(trigger, uuid=make_double_uuid(self.uuid))
        self.triggers.append(trigger)

    def add_action(
        self,
        name: str,
        costs: Sequence[Effect],
        effects: Sequence[Effect],
        is_private: bool,
        filters: Sequence[Filter],
    ) -> None:
        if not self._write:
            raise Exception(f"Can't add action to non-writable gadget")
        self.actions.append(
            Action(
                uuid=make_double_uuid(self.uuid),
                name=name,
                costs=costs,
                effects=effects,
                is_private=is_private,
                filters=filters,
            )
        )

    def add_action_object(self, action: Action) -> None:
        if not self._write:
            raise Exception(f"Can't add action to non-writable gadget")
        action = dataclasses_replace(action, uuid=make_double_uuid(self.uuid))
        self.actions.append(action)


class TurnFlags(Enum):
    ACTED = enum_auto()
    HAD_TRAVEL_ENCOUNTER = enum_auto()
    BAD_REP_CHECKED = enum_auto()


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
        travel_deck: List[TravelCard]
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
            if type_val == EffectType.ADD_EMBLEM:
                return snapshot_Gadget
            elif type_val == EffectType.QUEUE_ENCOUNTER:
                return Optional[TemplateCard]
            elif type_val in (
                EffectType.MODIFY_JOB,
                EffectType.MODIFY_LOCATION,
            ):
                return str
            else:
                return int
