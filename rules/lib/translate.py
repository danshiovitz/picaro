from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, TypeVar

from picaro.common.hexmap.types import CubeCoordinate, OffsetCoordinate
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.types.common import (
    Action,
    EffectType,
    Encounter,
    FullCardType,
    Route,
    RouteType,
    TableauCard,
)
from picaro.rules.types.snapshot import (
    Action as snapshot_Action,
    Board as snapshot_Board,
    Character as snapshot_Character,
    Country as snapshot_Country,
    Encounter as snapshot_Encounter,
    EncounterType as snapshot_EncounterType,
    Entity as snapshot_Entity,
    Gadget as snapshot_Gadget,
    Game as snapshot_Game,
    Hex as snapshot_Hex,
    Job as snapshot_Job,
    Record as snapshot_Record,
    TableauCard as snapshot_TableauCard,
    TemplateDeck as snapshot_TemplateDeck,
)
from picaro.rules.types.store import (
    Character,
    Country,
    Entity,
    Gadget,
    Game,
    Hex,
    Job,
    Record,
    TemplateDeck,
    Token,
)


def from_snapshot_entity(
    snapshot_entity: snapshot_Entity,
) -> Tuple[Entity, List[Gadget], List[Token]]:
    entity = from_snapshot_helper(snapshot_entity, Entity)
    gadgets = [from_snapshot_gadget(g, entity.uuid) for g in snapshot_entity.gadgets]
    tokens = [
        Token.create_detached(entity=entity.uuid, location=loc)
        for loc in snapshot_entity.locations
    ]
    return entity, gadgets, tokens


def to_snapshot_entity(entity: Entity, details: bool) -> snapshot_Entity:
    gadgets = []
    if details:
        gadgets = [to_snapshot_gadget(g) for g in Gadget.load_for_entity(entity.uuid)]
    locations = [t.location for t in Token.load_all_by_entity(entity.uuid)]

    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["gadgets"] = gadgets
        field_map["locations"] = locations

    return to_snapshot_helper(entity, snapshot_Entity, modify)


def to_snapshot_game(game: Game) -> snapshot_Game:
    return to_snapshot_helper(game, snapshot_Game)


def to_snapshot_hex(hx: Hex) -> snapshot_Hex:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["coordinate"] = CubeCoordinate(
            x=extra["x"], y=extra["y"], z=extra["z"]
        ).to_offset()

    return to_snapshot_helper(hx, snapshot_Hex, modify)


def from_snapshot_hex(hx: snapshot_Hex) -> Hex:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        cc = CubeCoordinate.from_row_col(
            extra["coordinate"].row, extra["coordinate"].column
        )
        field_map["x"] = cc.x
        field_map["y"] = cc.y
        field_map["z"] = cc.z

    return from_snapshot_helper(hx, Hex, modify)


def to_snapshot_country(country: Country) -> snapshot_Country:
    return to_snapshot_helper(country, snapshot_Country)


def from_snapshot_country(country: snapshot_Country) -> Country:
    return from_snapshot_helper(country, Country)


def to_snapshot_gadget(gadget: Gadget) -> snapshot_Gadget:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["actions"] = tuple(
            to_snapshot_action(a) for a in field_map["actions"]
        )

    return to_snapshot_helper(gadget, snapshot_Gadget, modify)


def from_snapshot_gadget(
    gadget: snapshot_Gadget, entity_uuid: Optional[str] = None
) -> Gadget:
    overlays = []
    triggers = []
    actions = []

    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        nonlocal overlays, triggers, actions
        overlays = field_map["overlays"]
        field_map["overlays"] = []
        triggers = field_map["triggers"]
        field_map["triggers"] = []
        actions = field_map["actions"]
        field_map["actions"] = []
        if entity_uuid:
            field_map["entity"] = entity_uuid

    ret = from_snapshot_helper(gadget, Gadget, modify)
    # now add in the subthings so they get the correct uuid:
    for overlay in overlays:
        ret.add_overlay_object(from_snapshot_overlay(overlay))
    for trigger in triggers:
        ret.add_trigger_object(from_snapshot_trigger(trigger))
    for action in actions:
        ret.add_action_object(from_snapshot_action(action))
    return ret


def from_snapshot_action(action: snapshot_Action) -> Action:
    return from_snapshot_helper(action, Action)


def to_snapshot_action(
    action: Action, route: Optional[Sequence[str]] = None
) -> snapshot_Action:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["route"] = route

    return to_snapshot_helper(action, snapshot_Action, modify)


def from_snapshot_template_deck(deck: snapshot_TemplateDeck) -> TemplateDeck:
    return from_snapshot_helper(deck, TemplateDeck)


def to_snapshot_job(job: Job) -> snapshot_Job:
    return to_snapshot_helper(job, snapshot_Job)


def from_snapshot_job(job: snapshot_Job) -> Job:
    return from_snapshot_helper(job, Job)


def to_snapshot_record(record: Record) -> snapshot_Record:
    return to_snapshot_helper(record, snapshot_Record)


def from_snapshot_record(record: snapshot_Record) -> Record:
    return from_snapshot_helper(record, Record)


def to_snapshot_character(ch: Character) -> snapshot_Character:
    entity = Entity.load(ch.uuid)
    location = Token.load_single_by_entity(ch.uuid).location
    routes = BoardRules.best_routes(location, {c.location for c in ch.tableau})
    all_skills = Game.load().skills
    emblems = Gadget.load_for_entity(ch.uuid)
    return snapshot_Character(
        uuid=ch.uuid,
        name=entity.name,
        player_uuid=ch.player_uuid,
        skills={sk: CharacterRules.get_skill_rank(ch, sk) for sk in all_skills},
        skill_xp={sk: ch.skill_xp.get(sk, 0) for sk in all_skills},
        job=ch.job_name,
        health=ch.health,
        max_health=CharacterRules.get_max_health(ch),
        coins=ch.coins,
        resources=ch.resources,
        max_resources=CharacterRules.get_max_resources(ch),
        reputation=ch.reputation,
        location=location,
        remaining_turns=ch.remaining_turns,
        acted_this_turn=ch.acted_this_turn(),
        luck=ch.luck,
        speed=ch.speed,
        max_speed=CharacterRules.get_init_speed(ch),
        tableau=tuple(
            to_snapshot_tableau_card(c, routes[c.location]) for c in ch.tableau
        ),
        encounter=to_snapshot_encounter(ch.encounter) if ch.encounter else None,
        queued=tuple(ch.queued),
        emblems=[to_snapshot_gadget(g) for g in emblems],
    )


def to_snapshot_tableau_card(
    card: TableauCard, route: Sequence[str]
) -> Sequence[snapshot_TableauCard]:
    if card.card.type == FullCardType.CHALLENGE:
        # in the future might be able to preview more checks so leaving them as lists
        data = card.card.data[0:1]
    elif card.card.type == FullCardType.CHOICE:
        data = "choice"
    elif card.card.type == FullCardType.SPECIAL:
        data = card.card.data

    return snapshot_TableauCard(
        uuid=card.card.uuid,
        name=card.card.name,
        type=card.card.type,
        data=data,
        age=card.age,
        location=card.location,
        route=Route(type=RouteType.NORMAL, steps=tuple(route)),
    )


def to_snapshot_encounter(encounter: Encounter) -> Sequence[snapshot_Encounter]:
    card_type = snapshot_EncounterType[encounter.card.type.name]
    return snapshot_Encounter(
        uuid=encounter.card.uuid,
        name=encounter.card.name,
        desc=encounter.card.desc,
        type=card_type,
        data=encounter.card.data,
        signs=encounter.card.signs,
        rolls=encounter.rolls,
    )


T = TypeVar("T")
S = TypeVar("S")


def to_snapshot_helper(
    val: T,
    snapshot_cls: Type[S],
    modify: Callable[[Dict[str, Any], Dict[str, Any]], None] = lambda _d, _e: None,
) -> S:
    field_map: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    snapshot_fields = {f.name for f in dataclass_fields(snapshot_cls)}
    if is_dataclass(val):
        val_fields = {f.name for f in dataclass_fields(val)}
    else:
        val_fields = val.FIELDS
    for f in val_fields:
        cur = getattr(val, f)
        if f in snapshot_fields:
            field_map[f] = cur
        else:
            extra[f] = cur
    modify(field_map, extra)
    return snapshot_cls(**field_map)


def from_snapshot_helper(
    snapshot: S,
    val_cls: Type[T],
    modify: Callable[[Dict[str, Any], Dict[str, Any]], None] = lambda _d, _e: None,
) -> T:
    field_map: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    snapshot_fields = {f.name for f in dataclass_fields(snapshot)}
    if is_dataclass(val_cls):
        val_fields = {f.name for f in dataclass_fields(val_cls)}
        create_val = lambda fm: val_cls(**fm)
    else:
        val_fields = val_cls.FIELDS
        create_val = lambda fm: val_cls.create_detached(**fm)
    for sf in snapshot_fields:
        cur = getattr(snapshot, sf)
        if sf in val_fields:
            field_map[sf] = cur
        else:
            extra[sf] = cur
    modify(field_map, extra)
    return create_val(field_map)
