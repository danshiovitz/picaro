import dataclasses
import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from picaro.common.exceptions import IllegalMoveException
from picaro.common.utils import clamp, pop_func

from .board import BoardRules
from .include.gadget import (
    compute_overlay_value,
    compute_trigger_effects,
    compute_actions,
)
from .types.internal import (
    Character,
    Effect,
    Encounter,
    EncounterContextType,
    Entity,
    EntityType,
    Filter,
    FilterType,
    FullCard,
    FullCardType,
    Game,
    Hex,
    Job,
    JobType,
    OverlayType,
    Route,
    RouteType,
    TableauCard,
    Token,
    Trigger,
    TriggerType,
)


class CharacterRules:
    @classmethod
    def create(cls, ch_uuid: str, player_uuid: str, job_name: str) -> None:
        Character.create(
            uuid=ch_uuid,
            player_uuid=player_uuid,
            job_name=job_name,
            skill_xp={},
            health=0,
            coins=0,
            resources={},
            reputation=0,
            remaining_turns=0,
            luck=0,
            turn_flags=set(),
            speed=0,
            tableau=[],
            encounter=None,
            queued=[],
            job_deck=[],
            travel_special_deck=[],
            camp_deck=[],
        )

        with Character.load_for_write(ch_uuid) as ch:
            ch.health = cls.get_max_health(ch)
            ch.reputation = cls.get_init_reputation(ch)

    @classmethod
    def check_filters(cls, ch: Character, filters: Sequence[Filter]) -> None:
        for f in filters:
            cls._check_filter(ch, f, do_raise=True)

    @classmethod
    def get_relevant_actions(
        cls, ch: Character, radius: int = 5
    ) -> Tuple[List[Trigger], Dict[str, Route]]:
        actions: List[Trigger] = []
        routes: Dict[str, Route] = {}

        all_actions = compute_actions(ch.uuid)
        hexes = BoardRules.find_entity_neighbors(ch.uuid, 0, radius)
        dests: Dict[str, str] = {}

        for action in all_actions:
            geos = [cls._check_filter_nearby(ch, f, hexes) for f in action.filters]
            # if all the filters say global is ok, then the route is global
            if not geos or all(g is None for g in geos):
                actions.append(action)
                routes[action.uuid] = Route(type=RouteType.GLOBAL, steps=[])
                continue

            # otherwise disregard all the globals and just go with the hex sets
            geos = [g for g in geos if g is not None]
            kept = geos[0]
            for geo in geos:
                kept &= geo

            if not kept:
                actions.append(action)
                # arguably we shouldn't display the action, but let's do it anyway
                routes[action.uuid] = Route(type=RouteType.UNAVAILABLE, steps=[])
                continue

            # assume these are in order from closest to farthest, so pick the first
            for hx in hexes:
                if hx.name not in kept:
                    continue
                actions.append(action)
                dests[action.uuid] = hx.name
                break

        if len(actions) > len(routes):
            token = Token.load_single_for_entity(ch.uuid)
            best_routes = BoardRules.best_routes(
                token.location, {d for d in dests.values() if d is not None}
            )
            for action in actions:
                best = best_routes.get(dests.get(action.uuid, None), None)
                if best is not None:
                    routes[action.uuid] = Route(type=RouteType.NORMAL, steps=best)
        return actions, routes

    @classmethod
    def run_triggers(
        cls, ch: Character, type: TriggerType, subtype: Optional[str]
    ) -> List[Effect]:
        return compute_trigger_effects(
            ch.uuid,
            type,
            subtype,
            lambda f: cls._check_filter(ch, f, skip_overlays=True),
        )

    @classmethod
    def get_init_turns(cls, ch: Character) -> int:
        return cls._clamp_overlay(20, ch, OverlayType.INIT_TURNS, min=10, max=40)

    @classmethod
    def get_max_luck(cls, ch: Character) -> int:
        return cls._clamp_overlay(5, ch, OverlayType.MAX_LUCK, min=0, max=10)

    @classmethod
    def get_max_tableau_size(cls, ch: Character) -> int:
        return cls._clamp_overlay(3, ch, OverlayType.MAX_TABLEAU_SIZE, min=1, max=6)

    @classmethod
    def get_init_tableau_age(cls, ch: Character) -> int:
        return cls._clamp_overlay(3, ch, OverlayType.INIT_TABLEAU_AGE, min=1, max=10)

    @classmethod
    def get_max_health(cls, ch: Character) -> int:
        return cls._clamp_overlay(20, ch, OverlayType.MAX_HEALTH, min=1, max=40)

    @classmethod
    def get_init_reputation(cls, ch: Character) -> int:
        return cls._clamp_overlay(3, ch, OverlayType.INIT_REPUTATION, max=10)

    @classmethod
    def get_max_resources(cls, ch: Character) -> int:
        job = Job.load(ch.job_name)
        if job.type == JobType.LACKEY:
            base_limit = 1
        elif job.type == JobType.SOLO:
            base_limit = 3
        elif job.type == JobType.CAPTAIN:
            base_limit = 10
        elif job.type == JobType.KING:
            base_limit = 100
        else:
            raise Exception(f"Unknown job type: {job.type}")
        return cls._clamp_overlay(base_limit, ch, OverlayType.MAX_RESOURCES)

    @classmethod
    def get_max_tasks(cls, ch: Character) -> int:
        return 3

    @classmethod
    def get_max_oracles(cls, ch: Character) -> int:
        return 3

    @classmethod
    def get_skill_rank(
        cls, ch: Character, skill_name: str, skip_overlays: bool = False
    ) -> int:
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        xp = ch.skill_xp.get(skill_name, 0)
        if xp < 20:
            base_rank = 0
        elif 20 <= xp < 45:
            base_rank = 1
        elif 45 <= xp < 70:
            base_rank = 2
        elif 70 <= xp < 95:
            base_rank = 3
        elif 95 <= xp < 125:
            base_rank = 4
        else:
            base_rank = 5

        if skip_overlays:
            return base_rank
        return cls._clamp_overlay(
            base_rank, ch, OverlayType.SKILL_RANK, skill_name, max=6
        )

    @classmethod
    def get_reliable_skill(cls, ch: Character, skill_name: str) -> int:
        return cls._clamp_overlay(0, ch, OverlayType.RELIABLE_SKILL, skill_name, max=4)

    @classmethod
    def get_init_speed(cls, ch: Character) -> int:
        job = Job.load(ch.job_name)
        if job.type == JobType.LACKEY:
            return 0

        if job.type == JobType.SOLO:
            base_speed = 3
        elif job.type == JobType.CAPTAIN:
            base_speed = 2
        elif job.type == JobType.KING:
            base_speed = 1
        else:
            raise Exception(f"Unknown job type: {job.type}")
        return cls._clamp_overlay(base_speed, ch, OverlayType.INIT_SPEED)

    @classmethod
    def get_trade_price(cls, ch: Character, resource_name: str) -> int:
        return cls._clamp_overlay(
            5, ch, OverlayType.TRADE_PRICE, resource_name, min=1, max=10
        )

    @classmethod
    def _clamp_overlay(
        cls,
        base_value: int,
        ch: Character,
        type: OverlayType,
        subtype: Optional[str] = None,
        min: Optional[int] = 0,
        max: Optional[int] = None,
    ) -> int:
        return clamp(
            base_value
            + compute_overlay_value(
                ch.uuid,
                type,
                subtype,
                lambda f: cls._check_filter(ch, f, skip_overlays=True),
            ),
            min=min,
            max=max,
        )

    @classmethod
    def _check_filter(
        cls, ch: Character, filter: Filter, do_raise=False, skip_overlays=False
    ) -> bool:
        ns = "not " if filter.reverse else ""
        if filter.type == FilterType.SKILL_GTE:
            rank = cls.get_skill_rank(ch, filter.skill, skip_overlays=skip_overlays)
            if (rank >= filter.value) == filter.reverse:
                if not do_raise:
                    return False
                raise IllegalMoveException(
                    f"{filter.skill} is {rank} and must be {'less than' if filter.reverse else 'at least'} {filter.value}"
                )
            return True
        elif filter.type == FilterType.NEAR_HEX:
            dist = BoardRules.min_distance_from_entity_to_hex(ch.uuid, filter.hex)
            if (dist <= filter.distance) == filter.reverse:
                if not do_raise:
                    return False
                raise IllegalMoveException(
                    f"Distance from {filter.hex} is {dist} and must {ns}be within {filter.distance}"
                )
            return True
        elif filter.type == FilterType.NEAR_TOKEN:
            entity = Entity.load(filter.entity_uuid)
            dist = BoardRules.min_distance_from_entity_to_entity(ch.uuid, entity.uuid)
            if (dist <= filter.distance) == filter.reverse:
                if not do_raise:
                    return False
                raise IllegalMoveException(
                    f"Distance from {entity.name} is {dist} and must {ns}be within {filter.distance}"
                )
            return True
        elif filter.type == FilterType.IN_COUNTRY:
            hx = BoardRules.get_single_token_hex(ch.uuid)
            if (hx.country == filter.country) == filter.reverse:
                if not do_raise:
                    return False
                raise IllegalMoveException(
                    f"Country is {hx.country} and must {ns}be {filter.country}"
                )
            return True
        else:
            raise Exception(f"Unknown filter type: {filter.type.name}")

    @classmethod
    def _check_filter_nearby(
        cls,
        ch: Character,
        filter: Filter,
        hexes: Sequence[Hex],
        skip_overlays=False,
    ) -> Optional[Set[str]]:
        if filter.type == FilterType.SKILL_GTE:
            rank = cls.get_skill_rank(ch, filter.skill, skip_overlays=skip_overlays)
            if (rank >= filter.value) == filter.reverse:
                return set()  # impossible to ever pass this by moving around
            return None
        elif filter.type == FilterType.NEAR_HEX:
            chk = (
                lambda hx: (BoardRules.distance(hx.name, filter.hex) <= filter.distance)
                != filter.reverse
            )
            return {hx.name for hx in hexes if chk(hx)}
        elif filter.type == FilterType.NEAR_TOKEN:
            entity = Entity.load(filter.entity_uuid)
            chk = (
                lambda hx: (
                    BoardRules.min_distance_from_entity_to_hex(entity.uuid, hx.name)
                    <= filter.distance
                )
                != filter.reverse
            )
            return {hx.name for hx in hexes if chk(hx)}
        elif filter.type == FilterType.IN_COUNTRY:
            chk = lambda hx: (hx.country == filter.country) != filter.reverse
            return {hx.name for hx in hexes if chk(hx)}
        else:
            raise Exception(f"Unknown filter type: {filter.type.name}")

    @classmethod
    def switch_job(cls, ch: Character, job_name: str) -> None:
        ch.job_name = job_name
        ch.tableau = []
        ch.job_deck = []
        ch.reputation = cls.get_init_reputation(ch)

    @classmethod
    def find_promote_job(cls, ch: Character) -> Optional[str]:
        cur_job = Job.load(ch.job_name)
        if cur_job.promotions:
            return random.choice(cur_job.promotions)
        return None

    @classmethod
    def find_demote_job(cls, ch: Character) -> Optional[str]:
        cur_job = Job.load(ch.job_name)
        all_jobs = Job.load_all()
        lowers = [j for j in all_jobs if j.rank == cur_job.rank - 1]
        prevs = [j for j in lowers if cur_job.name in j.promotions]
        if prevs:
            return random.choice(prevs).name
        if lowers:
            return random.choice(lowers).name
        return cls.find_bad_job(cls, ch)

    @classmethod
    def find_bad_job(cls, ch: Character) -> Optional[str]:
        all_jobs = Job.load_all()
        worst = [j for j in all_jobs if j.rank == 0]
        if worst:
            return random.choice(worst).name
        return None
