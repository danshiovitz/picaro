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
            if record.new_amount > record.old_amount:
                return f"increased to {record.new_amount}"
            elif record.new_amount < record.old_amount:
                return f"decreased to {record.new_amount}"
            else:
                return f"remained at {record.new_amount}"

        is_you = False
        if record.type == EffectType.ADD_ENTITY:
            subj = record.entity.name
            poss = record.entity.name + "'s"
        elif record.type == EffectType.TICK_METER:
            entity = self.entities.get_by_uuid(record.entity_uuid)
            meter = [
                m
                for t in entity.titles
                for m in t.meters
                if m.uuid == record.meter_uuid
            ][0]
            subj = f"{entity.name}'s {meter.name}"
            poss = subj + "'s"
        else:
            if record.entity_uuid == ch.uuid:
                is_you = True
                subj = "You"
                poss = "Your"
            else:
                entity = self.entities.get_by_uuid(record.entity_uuid)
                subj = entity.name
                poss = subj + "'s"

        line = ""
        if record.type == EffectType.MODIFY_ACTIVITY:
            if not record.enabled:
                line = f"{poss} activity was used"
            else:
                line = f"{poss} activity was refreshed"
        elif record.type == EffectType.MODIFY_HEALTH:
            line = f"{poss} health has " + render_single_int(record)
        elif record.type == EffectType.MODIFY_COINS:
            line = f"{poss} coins have " + render_single_int(record)
        elif record.type == EffectType.MODIFY_REPUTATION:
            line = f"{poss} reputation has " + render_single_int(record)
        elif record.type == EffectType.MODIFY_XP:
            line = f"{poss} {record.skill or 'unassigned'} xp has " + render_single_int(
                record
            )
        elif record.type == EffectType.MODIFY_RESOURCES:
            if record.resource is None:
                line = f"{subj} gained {record.new_value} resource draws"
            else:
                line = f"{poss} {record.resource} resources have " + render_single_int(
                    record
                )
        elif record.type == EffectType.MODIFY_TURNS:
            line = f"{poss} remaining turns have " + render_single_int(record)
        elif record.type == EffectType.MODIFY_SPEED:
            line = f"{poss} speed has " + render_single_int(record)
        elif record.type == EffectType.MODIFY_LUCK:
            line = f"{poss} luck has " + render_single_int(record)
        elif record.type == EffectType.ADD_TITLE:
            line = f"{subj} gained the title {self.render_title(record.title)}"
        elif record.type == EffectType.ADD_ENTITY:
            line = f"{subj} has been created: {self.render_entity(record.entity)}"
        elif record.type == EffectType.QUEUE_ENCOUNTER:
            line = f"{subj} had the encounter {self.render_template_card(record.encounter)}"
        elif record.type == EffectType.MODIFY_LOCATION:
            if is_you:
                line = f"{subj} are "
            else:
                line = f"{subj} is "
            line += f"now in hex {record.new_hex}"
        elif record.type == EffectType.MODIFY_JOB:
            if is_you:
                line = f"{subj} have "
            else:
                line = f"{subj} has "
            line += f"become a {record.new_job_name}"
        elif record.type == EffectType.LEADERSHIP:
            if is_you:
                line = f"{subj} have "
            else:
                line = f"{subj} has "
            line += f"entered into a leadership challenge"
        elif record.type == EffectType.TICK_METER:
            line = f"{subj} has " + render_single_int(record)
        else:
            line += f"UNKNOWN EVENT TYPE: {record}"

        if record.comments:
            line += " (" + ", ".join(record.comments) + ")"
        line += "."
        return "* " + line

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
            ln += f"{eff.amount:+} "
            if subtype:
                ln += subtype + " "
            if eff.amount == 1 or eff.amount == -1 or coll:
                ln += word
            else:
                ln += word + "s"
            return ln

        entity = ""
        if hasattr(eff, "entity_uuid") and eff.entity_uuid != self.character.uuid:
            entity = f" for {self.entities.get_by_uuid(eff.entity_uuid).name}"

        if eff.type == EffectType.MODIFY_COINS:
            return _std_mod("coin") + entity
        elif eff.type == EffectType.MODIFY_XP:
            return _std_mod("xp", coll=True, subtype=eff.skill or "unassigned") + entity
        elif eff.type == EffectType.MODIFY_REPUTATION:
            return _std_mod("reputation", coll=True) + entity
        elif eff.type == EffectType.MODIFY_HEALTH:
            return _std_mod("health", coll=True) + entity
        elif eff.type == EffectType.MODIFY_RESOURCES:
            return (
                _std_mod("resource draw")
                if eff.resource is None
                else _std_mod("resource", subtype=eff.resource)
            ) + entity
        elif eff.type == EffectType.MODIFY_LUCK:
            return _std_mod("luck", coll=True) + entity
        elif eff.type == EffectType.MODIFY_TURNS:
            return _std_mod("turn") + entity
        elif eff.type == EffectType.MODIFY_SPEED:
            return _std_mod("speed", coll=True) + entity
        elif eff.type == EffectType.LEADERSHIP:
            return f"leadership challenge ({eff.amount:+}){entity}"
        elif eff.type == EffectType.TRANSPORT:
            return f"random transport ({eff.amount:+}){entity}"
        elif eff.type == EffectType.MODIFY_ACTIVITY:
            return ("use activity" if not eff.enabled else "refresh activity") + entity
        elif eff.type == EffectType.ADD_TITLE:
            return "add a title (" + self.render_title(eff.title) + ")" + entity
        elif eff.type == EffectType.ADD_ENTITY:
            return "add an entity (" + self.render_entity(eff.entity) + ")" + entity
        elif eff.type == EffectType.QUEUE_ENCOUNTER:
            return (
                "queue an encounter ("
                + self.render_template_card(eff.encounter)
                + ")"
                + entity
            )
        elif eff.type == EffectType.MODIFY_LOCATION:
            return f"move to {eff.location}{entity}"
        elif eff.type == EffectType.MODIFY_JOB:
            return f"change job to {eff.job_name}{entity}"
        else:
            return eff

    def render_title(self, title: Title) -> str:
        ret = title.name or "<innate>"
        if title.overlays:
            ret += f" ({'; '.join(self.render_overlay(f) for f in title.overlays)})"
        if title.triggers:
            ret += f" ({'; '.join(self.render_trigger(f) for f in title.triggers)})"
        if title.actions:
            ret += f" ({'; '.join(self.render_action(f) for f in title.actions)})"
        if title.meters:
            ret += f" ({'; '.join(self.render_meter(f) for f in title.meters)})"
        return ret

    def render_title_extended(self, title: Title) -> List[str]:
        ret = []
        if title.name:
            ret.append(title.name + ":")
        for v in title.overlays:
            ret.append("* " + self.render_overlay(v))
        for v in title.triggers:
            ret.append("* " + self.render_trigger(v))
        for v in title.actions:
            ret.append("* " + self.render_action(v))
        for v in title.meters:
            ret.append("* " + self.render_meter(v))
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
            OverlayType.TRADE_PRICE: "trade price",
        }
        name = names.get(overlay.type, overlay.type.name)
        if isinstance(overlay, SkillAmountOverlay):
            name = overlay.skill + " " + name
        elif isinstance(overlay, ResourceAmountOverlay):
            name = overlay.resource + " " + name
        val = f"{overlay.value:+} {name}"
        if overlay.filters:
            val += f" if {', '.join(self.render_filter(f) for f in overlay.filters)}"
        return val

    def render_trigger(self, trigger: Trigger) -> str:
        names = {
            TriggerType.ENTER_HEX: "move to a new hex",
            TriggerType.START_TURN: "start a turn",
            TriggerType.END_TURN: "end a turn",
        }
        name = names.get(trigger.type, trigger.type.name)
        if isinstance(trigger, HexTrigger):
            name = trigger.hex + " " + name
        val = f"when you {name}: "
        val += ", ".join(self.render_effect(e) for e in trigger.effects)
        if trigger.filters:
            val += f" if {', '.join(self.render_filter(f) for f in trigger.filters)}"
        return val

    def render_action(self, action: Action) -> str:
        val = f"on action {action.name}: "
        if action.costs:
            val += "pay "
            val += ", ".join(self.render_effect(e) for e in action.costs)
        if action.costs and action.effects:
            val += " to "
        if action.effects:
            val += ", ".join(self.render_effect(e) for e in action.effects)
        if action.filters:
            val += f" if {', '.join(self.render_filter(f) for f in action.filters)}"
        return val

    def render_meter(self, meter: Meter) -> str:
        return (
            f"meter {meter.name} @ {meter.cur_value} "
            f"({meter.min_value} - {meter.max_value})"
        )

    def render_filter(self, filter: Filter) -> str:
        ns = "not " if filter.reverse else ""
        if filter.type == FilterType.SKILL_GTE:
            if filter.reverse:
                return f"{filter.skill} < {filter.value}"
            else:
                return f"{filter.skill} >= {filter.value}"
        elif filter.type == FilterType.NEAR_HEX:
            return f"{ns}within {filter.distance} hexes of {filter.hex}"
        elif filter.type == FilterType.NEAR_TOKEN:
            name = self.entities.get_by_uuid(filter.entity_uuid).name
            return f"{ns}within {filter.distance} hexes of {name}"
        elif filter.type == FilterType.IN_COUNTRY:
            return f"{ns}within {filter.country}"
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

    def render_entity_brief(self, entity: Entity) -> str:
        if entity.type == EntityType.CHARACTER:
            if entity.locations:
                return f"{entity.name} (in {entity.locations[0]})"
            else:
                return f"{entity.name} (nowhere)"
        elif entity.type == EntityType.LANDMARK or entity.type == EntityType.EVENT:
            ret = entity.name
            if entity.subtype:
                ret += f", a {entity.subtype}"
            if entity.locations:
                ret += f" (in {', '.join(entity.locations)})"
            return ret
        else:
            return str(entity)

    def render_entity_extended(self, entity: Entity) -> List[str]:
        ret: List[str] = []
        if entity.type == EntityType.CHARACTER:
            if entity.locations:
                ret.append(f"{entity.name} (in {entity.locations[0]})")
            else:
                ret.append(f"{entity.name} (nowhere)")
        elif entity.type == EntityType.LANDMARK or entity.type == EntityType.EVENT:
            ln = entity.name
            if entity.subtype:
                ln += f", a {entity.subtype}"
            if entity.locations:
                ln += f" (in {', '.join(entity.locations)})"
            ret.append(ln)
        else:
            raise Exception(f"Unknown entity type: {entity}")

        if len(entity.titles) > 1:
            print("Titles:")
        for title in entity.titles:
            ret.extend(self.render_title_extended(title))
        return ret
