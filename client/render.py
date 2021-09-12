from typing import Optional

from picaro.server.api_types import *


def render_record(ch: Character, record: Record) -> str:
    def render_single_int(record: Record) -> str:
        if record.new_value > record.old_value:
            return f"increased to {record.new_value}"
        elif record.new_value < record.old_value:
            return f"decreased to {record.new_value}"
        else:
            return f"remained at {record.new_value}"

    line = "* "
    subj = record.entity_name
    if record.entity_type == EntityType.CHARACTER and record.entity_name == ch.name:
        line += "Your "
        subj = "You"
    else:
        line += record.entity_name + "'s "

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
    elif record.type == EffectType.ADD_EMBLEM:
        if record.old_value:
            line += f"emblem was updated to {render_emblem(record.new_value)}."
        else:
            line = f"* {subj} gained the emblem {render_emblem(record.new_value)}"
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
        if record.new_value:
            line += f"lost in a leadership challenge"
        else:
            line += f"survived a leadership challenge"
    elif record.type == EffectType.START_TASK:
        # in the record the project is the subject and the character is the
        # object, but we want to display it the other way around
        if record.new_value == ch.name:
            line = f"* You have "
        else:
            line = f"* {record.new_value} has "
        line += f"started the task {record.entity_name}"
    elif record.type == EffectType.RETURN_TASK:
        # in the record the project is the subject and the character is the
        # object, but we want to display it the other way around
        if record.new_value == ch.name:
            line = f"* You have "
        else:
            line = f"* {record.new_value} has "
        line += f"returned the task {record.entity_name}"
    else:
        line += f"UNKNOWN EVENT TYPE: {record}"

    if record.comments:
        line += " (" + ", ".join(record.comments) + ")"
    line += "."
    return line


def render_encounter_effect(eff: EncounterEffect) -> str:
    names = {
        EncounterEffect.NOTHING: "nothing",
        EncounterEffect.GAIN_COINS: "+coins",
        EncounterEffect.GAIN_XP: "+xp",
        EncounterEffect.GAIN_REPUTATION: "+reputation",
        EncounterEffect.GAIN_HEALING: "+healing",
        EncounterEffect.GAIN_RESOURCES: "+resources",
        EncounterEffect.GAIN_TURNS: "+turns",
        EncounterEffect.GAIN_PROJECT_XP: "+project",
        EncounterEffect.GAIN_SPEED: "+speed",
        EncounterEffect.LOSE_COINS: "-coins",
        EncounterEffect.LOSE_REPUTATION: "-reputation",
        EncounterEffect.DAMAGE: "-damage",
        EncounterEffect.LOSE_RESOURCES: "-resources",
        EncounterEffect.LOSE_TURNS: "-turns",
        EncounterEffect.LOSE_SPEED: "-speed",
        EncounterEffect.LOSE_LEADERSHIP: "-leadership",
        EncounterEffect.TRANSPORT: "-transport",
    }
    return names.get(eff, eff.name)


def render_effect(eff: Effect) -> str:
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
    if eff.entity_name:
        entity = f" for {eff.entity_name}"

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
        return "add an emblem (" + render_emblem(eff.value) + ")" + entity
    elif eff.type == EffectType.MODIFY_LOCATION:
        return f"move to {eff.value}{entity}"
    elif eff.type == EffectType.MODIFY_JOB:
        return f"change job to {eff.value}{entity}"
    elif eff.type == EffectType.START_TASK:
        return f"start task {eff.value}{entity}"
    elif eff.type == EffectType.RETURN_TASK:
        return f"return task {eff.value}{entity}"
    else:
        return eff


def render_emblem(emblem: Emblem) -> str:
    ret = emblem.name
    if emblem.rules:
        ret += f" ({', '.join(render_rule(f) for f in emblem.rules)})"
    return ret


def render_rule(rule: Rule) -> str:
    names = {
        HookType.INIT_SPEED: "init speed",
        HookType.INIT_TABLEAU_AGE: "tableau age",
        HookType.INIT_TURNS: "init turns",
        HookType.MAX_HEALTH: "max health",
        HookType.MAX_LUCK: "max luck",
        HookType.MAX_TABLEAU_SIZE: "tableau size",
        HookType.SKILL_RANK: "rank",
        HookType.RELIABLE_SKILL: "reliability",
        HookType.MAX_RESOURCES: "resource limit",
    }
    name = names.get(rule.hook, rule.hook.name)
    if rule.subtype:
        name = rule.subtype + " " + name
    return f"{rule.value:+} {name}"
