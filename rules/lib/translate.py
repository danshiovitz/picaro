from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, TypeVar

from picaro.common.hexmap.types import CubeCoordinate, OffsetCoordinate
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.types.external import (
    Action as external_Action,
    Character as external_Character,
    Country as external_Country,
    Encounter as external_Encounter,
    EncounterType as external_EncounterType,
    Entity as external_Entity,
    Gadget as external_Gadget,
    Game as external_Game,
    Hex as external_Hex,
    Job as external_Job,
    Record as external_Record,
    TableauCard as external_TableauCard,
    TemplateDeck as external_TemplateDeck,
)
from picaro.rules.types.internal import (
    Action,
    Character,
    Country,
    EffectType,
    Encounter,
    Entity,
    FullCardType,
    Gadget,
    Game,
    Hex,
    Job,
    Record,
    Route,
    RouteType,
    TableauCard,
    TemplateDeck,
    Token,
)


def from_external_entity(
    external_entity: external_Entity,
) -> Tuple[Entity, List[Gadget], List[Token]]:
    entity = from_external_helper(external_entity, Entity)
    gadgets = [from_external_gadget(g, entity.uuid) for g in external_entity.gadgets]
    tokens = [
        Token.create_detached(entity=entity.uuid, location=loc)
        for loc in external_entity.locations
    ]
    return entity, gadgets, tokens


def to_external_entity(entity: Entity, details: bool) -> external_Entity:
    gadgets = []
    if details:
        gadgets = [to_external_gadget(g) for g in Gadget.load_for_entity(entity.uuid)]
    locations = [t.location for t in Token.load_all_by_entity(entity.uuid)]

    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["gadgets"] = gadgets
        field_map["locations"] = locations

    return to_external_helper(entity, external_Entity, modify)


def to_external_game(game: Game) -> external_Game:
    return to_external_helper(game, external_Game)


def to_external_hex(hx: Hex) -> external_Hex:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["coordinate"] = CubeCoordinate(
            x=extra["x"], y=extra["y"], z=extra["z"]
        ).to_offset()

    return to_external_helper(hx, external_Hex, modify)


def from_external_hex(hx: external_Hex) -> Hex:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        cc = CubeCoordinate.from_row_col(
            extra["coordinate"].row, extra["coordinate"].column
        )
        field_map["x"] = cc.x
        field_map["y"] = cc.y
        field_map["z"] = cc.z

    return from_external_helper(hx, Hex, modify)


def to_external_country(country: Country) -> external_Country:
    return to_external_helper(country, external_Country)


def from_external_country(country: external_Country) -> Country:
    return from_external_helper(country, Country)


def to_external_gadget(gadget: Gadget) -> external_Gadget:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["actions"] = tuple(
            to_external_action(a) for a in field_map["actions"]
        )

    return to_external_helper(gadget, external_Gadget, modify)


def from_external_gadget(
    gadget: external_Gadget, entity_uuid: Optional[str] = None
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

    ret = from_external_helper(gadget, Gadget, modify)
    # now add in the subthings so they get the correct uuid:
    for overlay in overlays:
        ret.add_overlay_object(from_external_overlay(overlay))
    for trigger in triggers:
        ret.add_trigger_object(from_external_trigger(trigger))
    for action in actions:
        ret.add_action_object(from_external_action(action))
    return ret


def from_external_action(action: external_Action) -> Action:
    return from_external_helper(action, Action)


def to_external_action(
    action: Action, route: Optional[Sequence[str]] = None
) -> external_Action:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["route"] = route

    return to_external_helper(action, external_Action, modify)


def from_external_template_deck(deck: external_TemplateDeck) -> TemplateDeck:
    return from_external_helper(deck, TemplateDeck)


def to_external_job(job: Job) -> external_Job:
    return to_external_helper(job, external_Job)


def from_external_job(job: external_Job) -> Job:
    return from_external_helper(job, Job)


def to_external_record(record: Record) -> external_Record:
    return to_external_helper(record, external_Record)


def from_external_record(record: external_Record) -> Record:
    return from_external_helper(record, Record)


def to_external_character(ch: Character) -> external_Character:
    entity = Entity.load(ch.uuid)
    location = Token.load_single_by_entity(ch.uuid).location
    routes = BoardRules.best_routes(location, {c.location for c in ch.tableau})
    all_skills = Game.load().skills
    emblems = Gadget.load_for_entity(ch.uuid)
    return external_Character(
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
            to_external_tableau_card(c, routes[c.location]) for c in ch.tableau
        ),
        encounter=to_external_encounter(ch.encounter) if ch.encounter else None,
        queued=tuple(ch.queued),
        emblems=[to_external_gadget(g) for g in emblems],
    )


def to_external_tableau_card(
    card: TableauCard, route: Sequence[str]
) -> Sequence[external_TableauCard]:
    if card.card.type == FullCardType.CHALLENGE:
        # in the future might be able to preview more checks so leaving them as lists
        data = card.card.data[0:1]
    elif card.card.type == FullCardType.CHOICE:
        data = "choice"
    elif card.card.type == FullCardType.SPECIAL:
        data = card.card.data

    return external_TableauCard(
        uuid=card.card.uuid,
        name=card.card.name,
        type=card.card.type,
        data=data,
        age=card.age,
        location=card.location,
        route=Route(type=RouteType.NORMAL, steps=tuple(route)),
    )


def to_external_encounter(encounter: Encounter) -> Sequence[external_Encounter]:
    card_type = external_EncounterType[encounter.card.type.name]
    return external_Encounter(
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


def to_external_helper(
    val: T,
    external_cls: Type[S],
    modify: Callable[[Dict[str, Any], Dict[str, Any]], None] = lambda _d, _e: None,
) -> S:
    field_map: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    external_fields = {f.name for f in dataclass_fields(external_cls)}
    if is_dataclass(val):
        val_fields = {f.name for f in dataclass_fields(val)}
    else:
        val_fields = val.FIELDS
    for f in val_fields:
        cur = getattr(val, f)
        if f in external_fields:
            field_map[f] = cur
        else:
            extra[f] = cur
    modify(field_map, extra)
    return external_cls(**field_map)


def from_external_helper(
    snapshot: S,
    val_cls: Type[T],
    modify: Callable[[Dict[str, Any], Dict[str, Any]], None] = lambda _d, _e: None,
) -> T:
    field_map: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    external_fields = {f.name for f in dataclass_fields(snapshot)}
    if is_dataclass(val_cls):
        val_fields = {f.name for f in dataclass_fields(val_cls)}
        create_val = lambda fm: val_cls(**fm)
    else:
        val_fields = val_cls.FIELDS
        create_val = lambda fm: val_cls.create_detached(**fm)
    for sf in external_fields:
        cur = getattr(snapshot, sf)
        if sf in val_fields:
            field_map[sf] = cur
        else:
            extra[sf] = cur
    modify(field_map, extra)
    return create_val(field_map)
