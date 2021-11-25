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
    Game as external_Game,
    Hex as external_Hex,
    Job as external_Job,
    Meter as external_Meter,
    Overlay as external_Overlay,
    Record as external_Record,
    TableauCard as external_TableauCard,
    TemplateDeck as external_TemplateDeck,
    Title as external_Title,
    Trigger as external_Trigger,
)
from picaro.rules.types.internal import (
    Character,
    Country,
    EffectType,
    Encounter,
    Entity,
    FullCardType,
    Game,
    Hex,
    Job,
    Meter,
    Overlay,
    Record,
    Route,
    RouteType,
    TableauCard,
    TemplateDeck,
    Token,
    Trigger,
    TriggerType,
)


def from_external_entity(
    external_entity: external_Entity,
) -> Tuple[Entity, List[Token], List[Overlay], List[Trigger], List[Meter]]:
    entity = from_external_helper(external_entity, Entity)
    tokens = [
        Token.create_detached(entity=entity.uuid, location=loc)
        for loc in external_entity.locations
    ]
    overlays, triggers, meters = from_external_titles(
        external_entity.titles, entity.uuid
    )
    return entity, tokens, overlays, triggers, meters


def to_external_entity(entity: Entity, details: bool) -> external_Entity:
    locations = [t.location for t in Token.load_all_by_entity(entity.uuid)]
    titles: List[external_Title] = []
    if details:
        overlays = Overlay.load_for_entity(entity.uuid)
        triggers = Trigger.load_for_entity(entity.uuid)
        meters = Meter.load_for_entity(entity.uuid)
        titles = to_external_titles(overlays, triggers, meters)

    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["locations"] = locations
        field_map["titles"] = titles

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


def from_external_overlay(
    overlay: external_Overlay, entity_uuid: str, title: Optional[str]
) -> Overlay:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["name"] = None
        field_map["entity_uuid"] = entity_uuid
        field_map["title"] = title

    return from_external_helper(overlay, Overlay, modify)


def to_external_overlay(overlay: Overlay) -> external_Overlay:
    return to_external_helper(overlay, external_Overlay)


def from_external_trigger(
    trigger: external_Trigger, entity_uuid: str, title: Optional[str]
) -> Trigger:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["name"] = None
        field_map["costs"] = ()
        field_map["entity_uuid"] = entity_uuid
        field_map["title"] = title

    return from_external_helper(trigger, Trigger, modify)


def to_external_trigger(trigger: Trigger) -> external_Trigger:
    return to_external_helper(trigger, external_Trigger)


def from_external_action(
    action: external_Action, entity_uuid: str, title: Optional[str]
) -> Trigger:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["type"] = TriggerType.ACTION
        field_map["entity_uuid"] = entity_uuid
        field_map["title"] = title

    return from_external_helper(
        action, Trigger, modify, indicator_val=TriggerType.ACTION
    )


def to_external_action(
    action: Trigger, route: Optional[Sequence[str]] = None
) -> external_Action:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["route"] = route

    if action.type != TriggerType.ACTION:
        raise Exception(
            f"Trying to convert non-action trigger to action: {action.uuid}"
        )
    return to_external_helper(action, external_Action, modify)


def from_external_meter(
    meter: external_Meter, entity_uuid: str, title: Optional[str]
) -> Meter:
    def modify(field_map: Dict[str, Any], extra: Dict[str, Any]) -> None:
        field_map["entity_uuid"] = entity_uuid
        field_map["title"] = title

    return from_external_helper(meter, Meter, modify)


def to_external_meter(meter: Meter) -> external_Meter:
    return to_external_helper(meter, external_Meter)


# titles don't actually have an internal representation
def to_external_titles(
    overlays: List[Overlay],
    triggers: List[Trigger],
    meters: List[Meter],
) -> List[external_Title]:
    title_map: Dict[
        Optional[str],
        Tuple[List[external_Overlay], List[external_Trigger], List[external_Action]],
    ] = {
        tt: ([], [], [], [])
        for tt in {o.title for o in overlays}
        | {t.title for t in triggers}
        | {t.title for t in meters}
    }
    for overlay in overlays:
        title_map[overlay.title][0].append(to_external_overlay(overlay))
    for trigger in triggers:
        if trigger.type == TriggerType.ACTION:
            title_map[trigger.title][2].append(to_external_action(trigger))
        else:
            title_map[trigger.title][1].append(to_external_trigger(trigger))
    for meter in meters:
        title_map[meter.title][3].append(to_external_meter(meter))
    return [
        external_Title(name=k, overlays=v[0], triggers=v[1], actions=v[2], meters=v[3])
        for k, v in title_map.items()
    ]


def from_external_titles(
    titles: List[external_Title], entity_uuid: str
) -> Tuple[List[Overlay], List[Trigger], List[Meter]]:
    overlays = []
    triggers = []
    meters = []

    for title in titles:
        for overlay in title.overlays:
            overlays.append(from_external_overlay(overlay, entity_uuid, title.name))
        for trigger in title.triggers:
            triggers.append(from_external_trigger(trigger, entity_uuid, title.name))
        for action in title.actions:
            triggers.append(from_external_action(action, entity_uuid, title.name))
        for meter in title.meters:
            meters.append(from_external_meter(meter, entity_uuid, title.name))
    return overlays, triggers, meters


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
    overlays = Overlay.load_for_entity(ch.uuid)
    triggers = Trigger.load_for_entity(ch.uuid)
    meters = Meter.load_for_entity(ch.uuid)
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
        titles=tuple(to_external_titles(overlays, triggers, meters)),
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

    external_cls = cls_to_subcls(external_cls, val)
    external_fields = {f.name for f in dataclass_fields(external_cls)}

    if is_dataclass(val):
        val_subcls = cls_to_subcls(val.__class__, val)
        val_fields = {f.name for f in dataclass_fields(val_subcls)}
    else:
        val_subcls = cls_to_subcls(val.Data, val)
        val_fields = val.Data.SUBCLASS_FIELDS.get(
            val_subcls, val.Data.BASE_FIELDS
        ).keys()

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
    indicator_val: Optional[Any] = None,
) -> T:
    field_map: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}

    external_cls = cls_to_subcls(snapshot.__class__, snapshot)
    external_fields = {f.name for f in dataclass_fields(external_cls)}

    if is_dataclass(val_cls):
        val_subcls = cls_to_subcls(val_cls, snapshot)
        val_fields = {f.name for f in dataclass_fields(val_subcls)}
        create_val = lambda fm: subtype_builder(val_cls, fm)
    else:
        val_subcls = cls_to_subcls(val_cls.Data, snapshot, indicator_val=indicator_val)
        val_fields = val_cls.Data.SUBCLASS_FIELDS.get(
            val_subcls, val_cls.Data.BASE_FIELDS
        ).keys()
        create_val = lambda fm: val_cls.create_detached(**fm)

    for sf in external_fields:
        cur = getattr(snapshot, sf)
        if sf in val_fields:
            field_map[sf] = cur
        else:
            extra[sf] = cur
    modify(field_map, extra)
    return create_val(field_map)


def cls_to_subcls(cls: Type[T], val: T, indicator_val: Optional[Any] = None) -> Type[T]:
    if not hasattr(cls, "SUBCLASS_INDICATOR"):
        return cls
    if indicator_val:
        type_val = indicator_val
    else:
        indicator = cls.SUBCLASS_INDICATOR
        type_val = getattr(val, indicator)
        if type_val not in cls.SUBCLASS_MAP:
            raise Exception(
                f"Can't find indicator ({type_val}) in subclass of {cls.__name__}"
            )
    return cls.SUBCLASS_MAP[type_val]
