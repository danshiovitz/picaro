from typing import Optional

from picaro.common.text import conj_list
from picaro.server.api_types import *
from .cache import LookupCache


def render_record(ch: Character, record: Record, cache: LookupCache) -> str:
    def render_single_int(record: Record) -> str:
        if record.new_value > record.old_value:
            return f"increased to {record.new_value}"
        elif record.new_value < record.old_value:
            return f"decreased to {record.new_value}"
        else:
            return f"remained at {record.new_value}"

    line = "* "
    subj = cache.lookup_entity(record.entity_uuid).name
    if record.entity_uuid == ch.uuid:
        line += "Your "
        subj = "You"
    else:
        line += subj + "'s "

    if record.type == EffectType.MODIFY_ACTIVITY:
        if record.new_value <= 0 and record.old_value > 0:
            line += "activity was used"
        elif record.new_value > 0 and record.old_value <= 0:
            line += "activity was refreshed"
        else:
            line += "activity is unchanged"
    elif record.type == EffectType.MODIFY_HEALTH:
        line += "health has " + render_single_int(record)
    elif record.type == EffectType.MODIFY_COINS:
        line += "coins have " + render_single_int(record)
    elif record.type == EffectType.MODIFY_REPUTATION:
        line += "reputation has " + render_single_int(record)
    elif record.type == EffectType.MODIFY_XP:
        line += f"{record.subtype or 'unassigned'} xp has " + render_single_int(record)
    elif record.type == EffectType.MODIFY_RESOURCES:
        if record.subtype is None:
            line = f"* {subj} gained {record.new_value} resource draws"
        else:
            line += f"{record.subtype} resources have " + render_single_int(record)
    elif record.type == EffectType.MODIFY_TURNS:
        line += "remaining turns have " + render_single_int(record)
    elif record.type == EffectType.MODIFY_SPEED:
        line += "speed has " + render_single_int(record)
    elif record.type == EffectType.MODIFY_LUCK:
        line += "luck has " + render_single_int(record)
    elif record.type == EffectType.ADD_EMBLEM:
        if record.old_value:
            line += f"emblem was updated to {render_gadget(record.new_value)}."
        else:
            line = f"* {subj} gained the emblem {render_gadget(record.new_value)}"
    elif record.type == EffectType.QUEUE_ENCOUNTER:
        line = f"* {subj} had the encounter {render_template_card(record.new_value)}"
    elif record.type == EffectType.MODIFY_LOCATION:
        if subj == "You":
            line = f"* {subj} are "
        else:
            line = f"* {subj} is "
        line += f"now in hex {record.new_value}"
    elif record.type == EffectType.MODIFY_JOB:
        if subj == "You":
            line = f"* {subj} have "
        else:
            line = f"* {subj} has "
        line += f"become a {record.new_value}"
    elif record.type == EffectType.LEADERSHIP:
        if subj == "You":
            line = f"* {subj} have "
        else:
            line = f"* {subj} has "
        if record.new_value <= 0:
            line += f"lost in a leadership challenge"
        elif record.new_value > 1:
            line += f"triumphed in a leadership challenge"
        else:
            line += f"survived a leadership challenge"
    else:
        line += f"UNKNOWN EVENT TYPE: {record}"

    if record.comments:
        line += " (" + ", ".join(record.comments) + ")"
    line += "."
    return line


def render_outcome(val: Outcome) -> str:
    names = {
        Outcome.NOTHING: "nothing",
        Outcome.GAIN_COINS: "+coins",
        Outcome.GAIN_XP: "+xp",
        Outcome.GAIN_REPUTATION: "+reputation",
        Outcome.GAIN_HEALING: "+healing",
        Outcome.GAIN_RESOURCES: "+resources",
        Outcome.GAIN_TURNS: "+turns",
        Outcome.GAIN_PROJECT_XP: "+project",
        Outcome.GAIN_SPEED: "+speed",
        Outcome.LOSE_COINS: "-coins",
        Outcome.LOSE_REPUTATION: "-reputation",
        Outcome.DAMAGE: "-damage",
        Outcome.LOSE_RESOURCES: "-resources",
        Outcome.LOSE_TURNS: "-turns",
        Outcome.LOSE_SPEED: "-speed",
        Outcome.LOSE_LEADERSHIP: "-leadership",
        Outcome.TRANSPORT: "-transport",
    }
    return names.get(val, val.name)


def render_effect(eff: Effect, cache: LookupCache) -> str:
    def _std_mod(word: str, coll: bool = False, subtype: Optional[str] = None) -> str:
        ln = "set to " if eff.is_absolute else ""
        ln += f"{eff.value:+} "
        if subtype:
            ln += subtype + " "
        if eff.value == 1 or eff.value == -1 or coll:
            ln += word
        else:
            ln += word + "s"
        return ln

    entity = ""
    if eff.entity_uuid:
        entity = f" for {cache.lookup_entity(eff.entity_uuid).name}"

    if eff.type == EffectType.MODIFY_COINS:
        return _std_mod("coin") + entity
    elif eff.type == EffectType.MODIFY_XP:
        return _std_mod("xp", coll=True, subtype=eff.subtype or "unassigned") + entity
    elif eff.type == EffectType.MODIFY_REPUTATION:
        return _std_mod("reputation", coll=True) + entity
    elif eff.type == EffectType.MODIFY_HEALTH:
        return _std_mod("health", coll=True) + entity
    elif eff.type == EffectType.MODIFY_RESOURCES:
        return (
            _std_mod("resource draw")
            if eff.subtype is None
            else _std_mod("resource", subtype=eff.subtype)
        ) + entity
    elif eff.type == EffectType.MODIFY_LUCK:
        return _std_mod("luck", coll=True) + entity
    elif eff.type == EffectType.MODIFY_TURNS:
        return _std_mod("turn") + entity
    elif eff.type == EffectType.MODIFY_SPEED:
        return _std_mod("speed", coll=True) + entity
    elif eff.type == EffectType.LEADERSHIP:
        return f"leadership challenge ({eff.value:+}){entity}"
    elif eff.type == EffectType.TRANSPORT:
        return f"random transport ({eff.value:+}){entity}"
    elif eff.type == EffectType.MODIFY_ACTIVITY:
        return ("use activity" if eff.value <= 0 else "refresh activity") + entity
    elif eff.type == EffectType.ADD_EMBLEM:
        return "add an emblem (" + render_gadget(eff.value) + ")" + entity
    elif eff.type == EffectType.QUEUE_ENCOUNTER:
        return "queue an encounter (" + render_template_card(eff.value) + ")" + entity
    elif eff.type == EffectType.MODIFY_LOCATION:
        return f"move to {eff.value}{entity}"
    elif eff.type == EffectType.MODIFY_JOB:
        return f"change job to {eff.value}{entity}"
    else:
        return eff


def render_gadget(gadget: Gadget) -> str:
    ret = gadget.name
    if gadget.overlays:
        ret += f" ({'; '.join(render_overlay(f) for f in gadget.overlays)})"
    return ret


def render_overlay(overlay: Overlay) -> str:
    names = {
        OverlayType.INIT_SPEED: "init speed",
        OverlayType.INIT_TABLEAU_AGE: "tableau age",
        OverlayType.INIT_TURNS: "init turns",
        OverlayType.MAX_HEALTH: "max health",
        OverlayType.MAX_LUCK: "max luck",
        OverlayType.MAX_TABLEAU_SIZE: "tableau size",
        OverlayType.SKILL_RANK: "rank",
        OverlayType.RELIABLE_SKILL: "reliability",
        OverlayType.MAX_RESOURCES: "resource limit",
    }
    name = names.get(overlay.type, overlay.type.name)
    if overlay.subtype:
        name = overlay.subtype + " " + name
    val = f"{overlay.value:+} {name}"
    if overlay.filters:
        val += f" if {', '.join(render_filter(f) for f in overlay.filters)}"
    return val


def render_filter(filter: Filter) -> str:
    if filter.type == FilterType.SKILL_GTE:
        return f"{filter.subtype} >= {filter.value}"
    elif filter.type == FilterType.NEAR_HEX:
        return f"within {filter.value} hexes of {filter.subtype}"
    elif filter.type == FilterType.IN_COUNTRY:
        return f"within {filter.subtype}"
    elif filter.type == FilterType.NOT_IN_COUNTRY:
        return f"not within {filter.subtype}"
    else:
        return str(filter)


def render_template_card(card: TemplateCard) -> str:
    return card.name
