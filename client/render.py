from collections import defaultdict
from typing import Optional

from picaro.common.hexmap.display import (
    DisplayInfo,
    OffsetCoordinate,
    render_simple,
    render_large,
)
from picaro.common.text import conj_list
from picaro.server.api_types import *

from .client_base import ClientBase
from .colors import colors


class RenderClientBase(ClientBase):
    TERRAINS = {
        "Forest": (colors.fg.green, '"'),
        "Jungle": (colors.bold + colors.fg.green, "%"),
        "Hills": (colors.fg.orange, "n"),
        "Mountains": (colors.fg.darkgrey, "^"),
        "Plains": (colors.fg.lightgrey, "."),
        "Desert": (colors.fg.yellow, ":"),
        "Water": (colors.fg.blue, "~"),
        "City": (colors.fg.red, "#"),
        "Swamp": (colors.fg.magenta, "&"),
        "Coastal": (colors.fg.cyan, ";"),
        "Arctic": (colors.bold, "/"),
    }

    def render_record(self, ch: Character, record: Record) -> str:
        def render_single_int(record: Record) -> str:
            if record.new_value > record.old_value:
                return f"increased to {record.new_value}"
            elif record.new_value < record.old_value:
                return f"decreased to {record.new_value}"
            else:
                return f"remained at {record.new_value}"

        line = "* "
        subj = self.entities.get_by_uuid(record.entity_uuid).name
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
            line += f"{record.subtype or 'unassigned'} xp has " + render_single_int(
                record
            )
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
                line += f"emblem was updated to {self.render_gadget(record.new_value)}."
            else:
                line = (
                    f"* {subj} gained the emblem {self.render_gadget(record.new_value)}"
                )
        elif record.type == EffectType.QUEUE_ENCOUNTER:
            line = f"* {subj} had the encounter {self.render_template_card(record.new_value)}"
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
            line += f"entered into a leadership challenge"
        else:
            line += f"UNKNOWN EVENT TYPE: {record}"

        if record.comments:
            line += " (" + ", ".join(record.comments) + ")"
        line += "."
        return line

    def render_outcome(self, val: Outcome) -> str:
        names = {
            Outcome.NOTHING: "nothing",
            Outcome.GAIN_COINS: "+coins",
            Outcome.GAIN_XP: "+xp",
            Outcome.GAIN_REPUTATION: "+reputation",
            Outcome.GAIN_HEALING: "+healing",
            Outcome.GAIN_RESOURCES: "+resources",
            Outcome.GAIN_TURNS: "+turns",
            Outcome.GAIN_SPEED: "+speed",
            Outcome.VICTORY: "+victory",
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

    def render_effect(self, eff: Effect) -> str:
        def _std_mod(
            word: str, coll: bool = False, subtype: Optional[str] = None
        ) -> str:
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
            entity = f" for {self.entities.get_by_uuid(eff.entity_uuid).name}"

        if eff.type == EffectType.MODIFY_COINS:
            return _std_mod("coin") + entity
        elif eff.type == EffectType.MODIFY_XP:
            return (
                _std_mod("xp", coll=True, subtype=eff.subtype or "unassigned") + entity
            )
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
            return "add an emblem (" + self.render_gadget(eff.value) + ")" + entity
        elif eff.type == EffectType.QUEUE_ENCOUNTER:
            return (
                "queue an encounter ("
                + self.render_template_card(eff.value)
                + ")"
                + entity
            )
        elif eff.type == EffectType.MODIFY_LOCATION:
            return f"move to {eff.value}{entity}"
        elif eff.type == EffectType.MODIFY_JOB:
            return f"change job to {eff.value}{entity}"
        else:
            return eff

    def render_gadget(self, gadget: Gadget) -> str:
        ret = gadget.name
        if gadget.overlays:
            ret += f" ({'; '.join(self.render_overlay(f) for f in gadget.overlays)})"
        return ret

    def render_overlay(self, overlay: Overlay) -> str:
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
            val += f" if {', '.join(self.render_filter(f) for f in overlay.filters)}"
        return val

    def render_filter(self, filter: Filter) -> str:
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

    def render_template_card(self, card: TemplateCard) -> str:
        return card.name

    def render_route(self, route: Route) -> str:
        if route.type == RouteType.GLOBAL:
            return "global"
        elif route.type == RouteType.UNAVAILABLE:
            return "unavailable"
        ret = route.steps[-1] if route.steps else self.character.location
        ret += f" - {len(route.steps)} away"
        if len(route.steps) > self.character.speed:
            ret += " (too far)"
        return ret

    def render_check(self, check: EncounterCheck) -> str:
        reward_name = self.render_outcome(check.reward)
        penalty_name = self.render_outcome(check.penalty)
        modifier = (
            check.modifier
            if check.modifier is not None
            else self.character.skills[check.skill]
        )
        ret = f"{check.skill} (1d8{modifier:+}) vs {check.target_number}"
        ret += f" ({reward_name} / {penalty_name})"
        return ret

    def render_small_map(
        self,
        center: Optional[OffsetCoordinate] = None,
        radius: int = 2,
        show_country: bool = False,
        show_encounters: bool = False,
    ) -> List[str]:
        coords = {hx.coordinate: hx for hx in self.hexes.get_all()}

        tokens: Dict[str, List[Entity]] = defaultdict(list)
        for entity in self.entities.get_all():
            for location in entity.locations:
                tokens[location].append(entity)

        encounters = (
            {card.location for card in self.character.tableau}
            if show_encounters
            else set()
        )

        flagged_hexes = set()

        def display(coord: OffsetCoordinate) -> str:
            hx = coords[coord]

            rev = colors.reverse if hx.name in flagged_hexes else ""

            if hx.name in tokens:
                if tokens[hx.name][0].type == EntityType.CHARACTER:
                    return colors.bold + "@" + colors.reset
                elif tokens[hx.name][0].type == EntityType.LANDMARK:
                    if tokens[hx.name][0].subtype == "city":
                        return colors.fg.red + rev + "#" + colors.reset
                    elif tokens[hx.name][0].subtype == "mine":
                        color = colors.bg.magenta + colors.fg.black + rev
                        return color + "*" + colors.reset
                    else:
                        return colors.bold + colors.bg.orange + rev + "?" + colors.reset
                else:
                    return colors.bold + colors.fg.green + rev + "?" + colors.reset
            elif hx.name in encounters:
                return colors.bold + colors.bg.red + rev + "!" + colors.reset

            color, symbol = self.TERRAINS[hx.terrain]
            if show_country:
                symbol = hx.country[0]
            return color + rev + symbol + colors.reset

        return render_simple(set(coords), 1, display, center=center, radius=radius)

    def render_large_map(
        self,
        entities: Dict[str, Entity],
        center: Optional[OffsetCoordinate] = None,
        radius: int = 2,
        show_country: bool = False,
        show_encounters: bool = False,
    ) -> List[str]:
        coords = {hx.coordinate: hx for hx in self.hexes.get_all()}

        def display(coord: OffsetCoordinate) -> DisplayInfo:
            hx = coords[coord]

            color, symbol = self.TERRAINS[hx.terrain]
            body1 = hx.name + " "
            if show_country:
                body2 = (hx.country + "     ")[0:5]
            else:
                body2 = (("*" * hx.danger) + "     ")[0:5]

            if hx.name in entities:
                body2 = (
                    colors.bold
                    + (entities[hx.name][0].name + "     ")[0:5]
                    + colors.reset
                )
            return DisplayInfo(
                fill=color + symbol + colors.reset,
                body1=body1,
                body2=body2,
            )

        return render_large(set(coords), display, center=center, radius=radius)
