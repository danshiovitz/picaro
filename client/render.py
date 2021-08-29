from typing import Optional

from picaro.server.api_types import *

def render_event(ch: Character, event: Event) -> str:
    def render_single_int(event: Event) -> str:
        if event.new_value > event.old_value:
            return f"increased to {event.new_value}"
        elif event.new_value < event.old_value:
            return f"decreased to {event.new_value}"
        else:
            return f"remained at {event.new_value}"

    line = "* "
    subj = event.entity_name
    if (
        event.entity_type == EntityType.CHARACTER
        and event.entity_name == ch.name
    ):
        line += "Your "
        subj = "You"
    else:
        line += event.entity_name + "'s "

    if event.type == EffectType.MODIFY_ACTION:
        if event.new_value <= 0 and event.old_value > 0:
            line += "action was used"
        elif event.new_value > 0 and event.old_value <= 0:
            line += "action was refreshed"
        else:
            line += "action is unchanged"
    elif event.type == EffectType.MODIFY_HEALTH:
        line += "health has " + render_single_int(event)
    elif event.type == EffectType.MODIFY_COINS:
        line += "coins have " + render_single_int(event)
    elif event.type == EffectType.MODIFY_REPUTATION:
        line += "reputation has " + render_single_int(event)
    elif event.type == EffectType.MODIFY_XP:
        line += f"{event.subtype or 'unassigned'} xp has " + render_single_int(
            event
        )
    elif event.type == EffectType.MODIFY_RESOURCES:
        if event.subtype is None:
            line = f"* {subj} gained {event.new_value} resource draws"
        else:
            line += f"{event.subtype} resources have " + render_single_int(
                event
            )
    elif event.type == EffectType.MODIFY_QUEST:
        line += "quest points have " + render_single_int(event)
    elif event.type == EffectType.MODIFY_TURNS:
        line += "remaining turns have " + render_single_int(event)
    elif event.type == EffectType.MODIFY_SPEED:
        line += "speed has " + render_single_int(event)
    elif event.type == EffectType.ADD_EMBLEM:
        if event.old_value:
            line += (
                f"emblem was updated to {render_emblem(event.new_value)}."
            )
        else:
            line = f"* {subj} gained the emblem {render_emblem(event.new_value)}"
    elif event.type == EffectType.MODIFY_LOCATION:
        if subj == "You":
            line = f"* {subj} are "
        else:
            line = f"* {subj} is "
        line += f"now in hex {event.new_value}"
    elif event.type == EffectType.MODIFY_JOB:
        if subj == "You":
            line = f"* {subj} have "
        else:
            line = f"* {subj} has "
        line += f"become a {event.new_value}"
    elif event.type == EffectType.DISRUPT_JOB:
        if subj == "You":
            line = f"* {subj} have "
        else:
            line = f"* {subj} has "
        if event.new_value:
            line += f"lost in a leadership challenge"
        else:
            line += f"survived a leadership challenge"
    elif event.type == EffectType.START_TASK:
        # in the event the project is the subject and the character is the
        # object, but we want to display it the other way around
        if event.new_value == ch.name:
            line = f"* You have "
        else:
            line = f"* {event.new_value} has "
        line += f"started the task {event.entity_name}"
    elif event.type == EffectType.RETURN_TASK:
        # in the event the project is the subject and the character is the
        # object, but we want to display it the other way around
        if event.new_value == ch.name:
            line = f"* You have "
        else:
            line = f"* {event.new_value} has "
        line += f"returned the task {event.entity_name}"
    else:
        line += f"UNKNOWN EVENT TYPE: {event}"

    if event.comments:
        line += " (" + ", ".join(event.comments) + ")"
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
        EncounterEffect.GAIN_QUEST: "+quest",
        EncounterEffect.GAIN_TURNS: "+turns",
        EncounterEffect.GAIN_PROJECT_XP: "+project",
        EncounterEffect.LOSE_COINS: "-coins",
        EncounterEffect.LOSE_REPUTATION: "-reputation",
        EncounterEffect.DAMAGE: "-damage",
        EncounterEffect.LOSE_RESOURCES: "-resources",
        EncounterEffect.LOSE_TURNS: "-turns",
        EncounterEffect.LOSE_SPEED: "-speed",
        EncounterEffect.DISRUPT_JOB: "-job",
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
        return _std_mod("xp", coll=True, subtype=eff.subtype or 'unassigned') + entity
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
    elif eff.type == EffectType.MODIFY_QUEST:
        return _std_mod("quest", coll=True) + entity
    elif eff.type == EffectType.MODIFY_TURNS:
        return _std_mod("turn") + entity
    elif eff.type == EffectType.MODIFY_SPEED:
        _std_mod("speed", coll=True) + entity
    elif eff.type == EffectType.DISRUPT_JOB:
        return f"job turmoil ({eff.value:+}){entity}"
    elif eff.type == EffectType.TRANSPORT:
        return f"random transport ({eff.value:+}){entity}"
    elif eff.type == EffectType.MODIFY_ACTION:
        return ("use action" if eff.value <= 0 else "refresh action") + entity
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
    if emblem.feats:
        ret += f" ({', '.join(render_feat(f) for f in emblem.feats)})"
    return ret


def render_feat(feat: Feat) -> str:
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
    name = names.get(feat.hook, feat.hook.name)
    if feat.subtype:
        name = feat.subtype + " " + name
    return f"{feat.value:+} {name}"
