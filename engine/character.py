import dataclasses
import random
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from itertools import groupby
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
)

from .board import ActiveBoard as Board
from .deck import load_deck
from .encounter import UpdateHolder
from .exceptions import BadStateException, IllegalMoveException
from .job import load_job, load_jobs
from .skills import load_skills
from .snapshot import (
    Character as snapshot_Character,
    Encounter as snapshot_Encounter,
    TableauCard as snapshot_TableauCard,
)
from .storage import ObjectStorageBase
from .types import (
    Choices,
    Effect,
    EffectType,
    Emblem,
    Encounter,
    EncounterActions,
    EncounterContextType,
    EncounterEffect,
    EncounterOutcome,
    EncounterSingleOutcome,
    Feat,
    FullCard,
    HookType,
    JobType,
    TableauCard,
    TemplateCard,
)


class Party:
    def create_character(
        self, name: str, player_id: int, job_name: str, board: Board, location: str
    ) -> None:
        ch = Character.create(name, player_id, job_name)
        board.add_token(name=name, type="Character", location=location)
        return CharacterStorage.create(ch)

    def get_character(self, name: str, board: Board) -> snapshot_Character:
        ch = CharacterStorage.load_by_name(name)
        all_skills = load_skills()
        location = board.get_token_location(ch.name)
        routes = board.best_routes(location, [c.location for c in ch.tableau])
        return snapshot_Character(
            name=ch.name,
            player_id=ch.player_id,
            skills={sk: ch.get_skill_rank(sk) for sk in all_skills},
            skill_xp={sk: ch.skill_xp.get(sk, 0) for sk in all_skills},
            job=ch.job_name,
            health=ch.health,
            max_health=ch.get_max_health(),
            coins=ch.coins,
            resources=ch.resources,
            max_resources=ch.get_max_resources(),
            reputation=ch.reputation,
            quest=ch.quest,
            location=location,
            remaining_turns=ch.remaining_turns,
            acted_this_turn=ch.acted_this_turn,
            luck=ch.luck,
            speed=ch.speed,
            max_speed=ch.get_init_speed(),
            tableau=tuple(
                self._tableau_snapshot(c, routes[c.location]) for c in ch.tableau
            ),
            encounters=tuple(self._encounter_snapshot(e) for e in ch.encounters),
            emblems=tuple(ch.emblems),
        )

    def _tableau_snapshot(
        self, card: TableauCard, route: Sequence[str]
    ) -> Sequence[snapshot_TableauCard]:
        # in the future might be able to preview more checks so leaving them as lists
        return snapshot_TableauCard(
            id=card.card.id,
            name=card.card.name,
            checks=card.card.checks[0:1],
            choices=card.card.choices,
            age=card.age,
            location=card.location,
            route=tuple(route),
        )

    def _encounter_snapshot(self, encounter: Encounter) -> Sequence[snapshot_Encounter]:
        return snapshot_Encounter(
            name=encounter.card.name,
            desc=encounter.card.desc,
            checks=encounter.card.checks,
            choices=encounter.card.choices,
            signs=encounter.card.signs,
            rolls=encounter.rolls,
        )

    def start_season(self, board: Board) -> None:
        for ch in CharacterStorage.load():
            ch.start_season(board)
            CharacterStorage.update(ch)

    def finish_season(self, board: Board) -> None:
        raise Exception("Not implemented yet")

    def do_job(self, name: str, card_id: str, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if ch.acted_this_turn:
            raise BadStateException("You have already acted this turn.")
        ch.acted_this_turn = True
        ch.speed = 0
        card = ch.remove_tableau_card(card_id)
        location = board.get_token_location(ch.name)
        if card.location != location:
            raise IllegalMoveException(
                f"You must be in hex {card.location} for that encounter."
            )
        ch.queue_encounter(card.card, context_type=EncounterContextType.JOB)
        CharacterStorage.update(ch)

    def token_action(
        self, name: str, token_name: str, action_name: str, board: Board
    ) -> None:
        ch = CharacterStorage.load_by_name(name)
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        location = board.get_token_location(ch.name)
        token = board.get_token(token_name)
        actions = [a for a in token.actions if a.name == action_name]
        if not actions:
            raise BadStateException(
                f"No such action {action_name} on token {token_name}."
            )
        action = actions[0]

        action_template = TemplateCard(
            copies=1,
            name=action.name,
            desc="...",
            choices=Choices(
                min_choices=0,
                max_choices=1,
                is_random=False,
                choice_list=[
                    action.benefit
                    + [dataclasses.replace(a, is_cost=True) for a in action.cost],
                ],
            ),
        )
        custom_deck = load_deck("Custom")
        card = custom_deck.make_card(action_template, 1, EncounterContextType.ACTION)

        ch.queue_encounter(card, context_type=EncounterContextType.ACTION)
        CharacterStorage.update(ch)

    def travel(self, name: str, step: str, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if ch.speed <= 0:
            raise IllegalMoveException(f"You have no remaining speed.")

        board.move_token(ch.name, step, adjacent=True)
        ch.speed -= 1

        if not ch.had_travel_encounter:
            card = ch.draw_travel_card(board.get_token_location(ch.name), board)
            if card:
                ch.queue_encounter(card, context_type=EncounterContextType.TRAVEL)
                ch.had_travel_encounter = True
        CharacterStorage.update(ch)

    def camp(self, name: str, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if ch.acted_this_turn:
            raise BadStateException("You have already acted this turn.")
        ch.acted_this_turn = True
        ch.speed = 0
        card = ch.draw_camp_card(board)
        ch.queue_encounter(card, context_type=EncounterContextType.CAMP)
        CharacterStorage.update(ch)

    def resolve_encounter(
        self, name: str, actions: EncounterActions, board: Board
    ) -> EncounterOutcome:
        ch = CharacterStorage.load_by_name(name)

        encounter = ch.pop_encounter()
        effects = ch.calc_effects(encounter, actions)
        outcome = ch.apply_effects(effects, encounter.context_type, board)
        if ch.acted_this_turn and not ch.encounters:
            ch.finish_turn(board)

        CharacterStorage.update(ch)
        return outcome

    def end_turn(self, name: str, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if ch.acted_this_turn:
            raise BadStateException("You have already acted this turn.")
        ch.finish_turn(board)
        CharacterStorage.update(ch)


class TravelCardType(Enum):
    NOTHING = enum_auto()
    DANGER = enum_auto()
    TRINKET = enum_auto()


@dataclass
class TravelCard:
    type: TravelCardType
    value: int = 0


def clamp(val: int, min: Optional[int] = None, max: Optional[int] = None) -> int:
    if min is not None and val < min:
        return min
    elif max is not None and val > max:
        return max
    else:
        return val


ModTuple = Tuple[Optional[int], Optional[int], str]


# This class is not frozen, and also not exposed externally - it needs to be loaded every time
# it's used and saved at the end
@dataclass
class Character:
    name: str
    player_id: int
    job_name: str
    skill_xp: Dict[str, int]
    health: int
    coins: int
    resources: Dict[str, int]
    reputation: int
    quest: int
    remaining_turns: int
    luck: int
    emblems: Sequence[Emblem]
    tableau: List[TableauCard]
    encounters: List[Encounter]
    job_deck: List[FullCard]
    travel_deck: List[TravelCard]
    camp_deck: List[FullCard]
    acted_this_turn: bool
    speed: int
    had_travel_encounter: bool

    @classmethod
    def create(cls, name: str, player_id: int, job_name: str) -> "Character":
        ch = Character(
            name=name,
            player_id=player_id,
            job_name=job_name,
            skill_xp={},
            health=0,
            coins=0,
            resources={},
            reputation=3,
            quest=0,
            remaining_turns=0,
            luck=0,
            emblems=[],
            tableau=[],
            encounters=[],
            job_deck=[],
            travel_deck=[],
            camp_deck=[],
            acted_this_turn=False,
            speed=0,
            had_travel_encounter=False,
        )
        ch.health = ch.get_max_health()
        ch.speed = ch.get_init_speed()
        return ch

    def get_init_turns(self) -> int:
        return clamp(20 + self._calc_hook(HookType.INIT_TURNS), min=10, max=40)

    def get_max_luck(self) -> int:
        return clamp(5 + self._calc_hook(HookType.MAX_LUCK), min=0)

    def get_max_tableau_size(self) -> int:
        return clamp(3 + self._calc_hook(HookType.MAX_TABLEAU_SIZE), min=1)

    def get_init_card_age(self) -> int:
        return clamp(3 + self._calc_hook(HookType.INIT_CARD_AGE), min=1)

    def get_max_health(self) -> int:
        return clamp(20 + self._calc_hook(HookType.MAX_HEALTH), min=1)

    def get_max_resources(self) -> int:
        job = load_job(self.job_name)
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
        return clamp(base_limit + self._calc_hook(HookType.MAX_RESOURCES), min=0)

    def get_skill_rank(self, skill_name: str) -> int:
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        xp = self.skill_xp.get(skill_name, 0)
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
        return clamp(
            base_rank + self._calc_hook(HookType.SKILL_RANK, skill_name), min=0, max=6
        )

    def get_init_speed(self) -> int:
        job = load_job(self.job_name)
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
        return clamp(base_speed + self._calc_hook(HookType.INIT_SPEED), min=0)

    def _calc_hook(self, hook_name: HookType, hook_param: Optional[str] = None) -> int:
        tot = 0
        for emblem in self.emblems:
            for feat in emblem.feats:
                if feat.hook == hook_name:
                    param_match = (
                        hook_param is None
                        or feat.param is None
                        or hook_param == feat.param
                    )
                    if param_match:
                        tot += feat.value
        return tot

    def start_season(self, board: Board) -> None:
        # leave the encounters queue alone, since there
        # might be stuff from the rumors phase
        self.tableau = []
        self.remaining_turns = self.get_init_turns()
        self.acted_this_turn = False
        self.had_travel_encounter = False
        self.luck = self.get_max_luck()
        self.refill_tableau(board)

    def refill_tableau(self, board: Board) -> None:
        job = load_job(self.job_name)
        while len(self.tableau) < self.get_max_tableau_size():
            if not self.job_deck:
                additional: List[TemplateCard] = []
                self.job_deck = job.make_deck(additional=additional)
            card = self.job_deck.pop(0)
            dst = random.choice(job.encounter_distances)
            location = random.choice(board.find_hexes_near_token(self.name, dst, dst))

            self.tableau.append(
                TableauCard(card=card, location=location, age=self.get_init_card_age())
            )

    def remove_tableau_card(self, card_id) -> TableauCard:
        idx = [
            i for i in range(len(self.tableau)) if self.tableau[i].card.id == card_id
        ]
        if not idx:
            raise BadStateException(f"No such encounter card found ({card_id})")
        return self.tableau.pop(idx[0])

    def queue_encounter(
        self,
        card: FullCard,
        context_type: EncounterContextType,
    ) -> None:
        rolls = []
        for chk in card.checks:
            bonus = self.get_skill_rank(chk.skill)
            roll_min = 0 + self._calc_hook(HookType.RELIABLE_SKILL, chk.skill)
            roll_val = clamp(random.randint(1, 8), min=roll_min, max=None)
            rolls.append(roll_val + bonus)
        if card.choices and card.choices.is_random:
            rolls.extend(
                random.randint(1, len(card.choices.choice_list))
                for _ in range(card.choices.max_choices)
            )
        self.encounters.append(
            Encounter(
                card=card,
                rolls=rolls,
                context_type=context_type,
            )
        )

    def pop_encounter(self) -> Encounter:
        if not self.encounters:
            raise BadStateException("There is no active encounter.")

        return self.encounters.pop(0)

    # translate the results of the encounter into absolute modifications
    def calc_effects(
        self, encounter: Encounter, actions: EncounterActions
    ) -> List[Effect]:
        self._validate_actions(encounter, actions)
        if actions.flee:
            return []

        ret = []

        if encounter.card.checks:
            ocs = defaultdict(int)
            failures = 0

            for idx, check in enumerate(encounter.card.checks):
                if encounter.rolls[idx] >= check.target_number:
                    ocs[check.reward] += 1
                else:
                    ocs[check.penalty] += 1
                    failures += 1

            mcs = defaultdict(int)

            sum_til = lambda v: (v * v + v) // 2
            for enc_eff, cnt in ocs.items():
                if enc_eff == EncounterEffect.GAIN_COINS:
                    ret.append(Effect(type=EffectType.MODIFY_COINS, value=sum_til(cnt)))
                elif enc_eff == EncounterEffect.LOSE_COINS:
                    ret.append(Effect(type=EffectType.MODIFY_COINS, value=-cnt))
                elif enc_eff == EncounterEffect.GAIN_REPUTATION:
                    ret.append(
                        Effect(type=EffectType.MODIFY_REPUTATION, value=sum_til(cnt))
                    )
                elif enc_eff == EncounterEffect.LOSE_REPUTATION:
                    ret.append(Effect(type=EffectType.MODIFY_REPUTATION, value=-cnt))
                elif enc_eff == EncounterEffect.GAIN_HEALING:
                    ret.append(Effect(type=EffectType.MODIFY_HEALTH, value=cnt * 3))
                elif enc_eff == EncounterEffect.DAMAGE:
                    ret.append(
                        Effect(type=EffectType.MODIFY_HEALTH, value=-sum_til(cnt))
                    )
                elif enc_eff == EncounterEffect.GAIN_QUEST:
                    ret.append(Effect(type=EffectType.MODIFY_QUEST, value=cnt))
                elif enc_eff == EncounterEffect.GAIN_XP:
                    ret.append(
                        Effect(
                            type=EffectType.MODIFY_XP,
                            param=encounter.card.checks[0].skill,
                            value=cnt * 5,
                        )
                    )
                elif enc_eff == EncounterEffect.GAIN_RESOURCES:
                    ret.append(Effect(type=EffectType.MODIFY_RESOURCES, value=cnt))
                elif enc_eff == EncounterEffect.LOSE_RESOURCES:
                    ret.append(Effect(type=EffectType.MODIFY_RESOURCES, value=-cnt))
                elif enc_eff == EncounterEffect.GAIN_TURNS:
                    ret.append(Effect(type=EffectType.MODIFY_TURNS, value=cnt))
                elif enc_eff == EncounterEffect.LOSE_TURNS:
                    ret.append(Effect(type=EffectType.MODIFY_TURNS, value=-cnt))
                elif enc_eff == EncounterEffect.LOSE_SPEED:
                    ret.append(Effect(type=EffectType.MODIFY_SPEED, value=-cnt))
                elif enc_eff == EncounterEffect.TRANSPORT:
                    ret.append(Effect(type=EffectType.TRANSPORT, value=cnt * 5))
                elif enc_eff == EncounterEffect.DISRUPT_JOB:
                    ret.append(Effect(type=EffectType.DISRUPT_JOB, value=-cnt))
                elif enc_eff == EncounterEffect.NOTHING:
                    pass
                else:
                    raise Exception(f"Unknown effect: {enc_eff}")
            if failures > 0:
                ret.append(
                    Effect(
                        type=EffectType.MODIFY_XP,
                        param=encounter.card.checks[0].skill,
                        value=failures,
                    )
                )

        for c in actions.choices:
            ret.extend(encounter.card.choices.choice_list[c])

        return ret

    # note this does update luck as well as validating stuff
    def _validate_actions(
        self, encounter: Encounter, actions: EncounterActions
    ) -> None:
        if encounter.card.checks:
            # validate the actions by rerunning them
            luck = self.luck
            rolls = encounter.rolls

            for adj in actions.adjusts or []:
                if luck <= 0:
                    raise BadStateException("Luck not high enough for adjust")
                luck -= 1
                rolls[adj] += 1

            for from_c, to_c in actions.transfers or []:
                if rolls[from_c] < 2:
                    raise BadStateException("From not enough for transfer")
                rolls[from_c] -= 2
                rolls[to_c] += 1

            if actions.flee:
                if luck <= 0:
                    raise BadStateException("Luck not high enough for flee")
                luck -= 1

            rolls = tuple(rolls)
            if (luck, rolls) != (actions.luck, actions.rolls):
                raise BadStateException("Computed luck/rolls doesn't match?")

            self.luck = luck

        if encounter.card.choices:
            choices = encounter.card.choices
            if len(actions.choices) < choices.min_choices:
                with_s = f"{choices.min_choices} choice"
                if choices.min_choices != 1:
                    with_s += "s"
                raise IllegalMoveException(f"Must supply at least {with_s}.")
            if len(actions.choices) > choices.max_choices:
                with_s = f"{choices.min_choices} choice"
                if choices.min_choices != 1:
                    with_s += "s"
                raise IllegalMoveException(f"Must supply at most {with_s}.")
            for idx, cur in enumerate(actions.choices):
                if choices.is_random and cur != encounter.rolls[idx] - 1:
                    raise BadStateException("Choice should match roll for random")
                elif cur < 0 or cur >= len(choices.choice_list):
                    raise BadStateException(f"Choice out of range: {cur}")
        elif actions.choices:
            raise BadStateException("Choices not allowed here.")

    def apply_effects(
        self,
        effects: List[Effect],
        context_type: EncounterContextType,
        board: Board,
    ) -> EncounterOutcome:
        # want something like: first process gain coins, if any, then process lose coins, if any,
        # then gain resources, then lose resources, ... , then job change, then pick the actual
        # transport location if any
        # we do it this way because we want, eg, to be able to overwrite reputation changes with
        # reputation set via job change (note that any 'set' overwrites previous comments, as well)
        effects_split = defaultdict(list)
        for effect in effects:
            effects_split[(effect.type, effect.param is None)].append(effect)

        def simple(
            name: str, effect_type: EffectType, max_val: Optional[int] = None
        ) -> UpdateHolder:
            get_f = lambda: getattr(self, name)
            set_f = lambda val: setattr(self, name, val)
            holder = UpdateHolder(
                name,
                effect_type,
                None,
                context_type,
                0,
                max_val,
                get_f=get_f,
                set_f=set_f,
            )
            holder.apply_effects(effects_split.pop((effect_type, True), []))
            return holder

        def dict_holder(name: str, effect_type: EffectType) -> Dict[str, UpdateHolder]:
            char_self = self

            class HolderDict(dict):
                def __missing__(self, param):
                    get_f = lambda: getattr(char_self, name).get(param, 0)
                    set_f = lambda val: getattr(char_self, name).update({param: val})
                    holder = UpdateHolder(
                        name,
                        effect_type,
                        param,
                        context_type,
                        0,
                        None,
                        get_f=get_f,
                        set_f=set_f,
                    )
                    self[param] = holder
                    return holder

            params = {e.param for e in effects if e.type == effect_type and e.param}
            ret = HolderDict()
            for param in params:
                ret[param].apply_effects(effects_split.pop((effect_type, False), []))
            return ret

        def const_val(
            name: str, effect_type: EffectType, init_val: int
        ) -> UpdateHolder:
            get_f = lambda: init_val
            set_f = lambda _val: None
            holder = UpdateHolder(
                name, effect_type, None, context_type, 0, None, get_f=get_f, set_f=set_f
            )
            holder.apply_effects(effects_split.pop((effect_type, True), []))
            return holder

        action_holder = const_val(
            "action_flag", EffectType.MODIFY_ACTION, 0 if self.acted_this_turn else 1
        )
        coins_holder = simple("coins", EffectType.MODIFY_COINS)
        reputation_holder = simple("reputation", EffectType.MODIFY_REPUTATION)
        health_holder = simple(
            "health", EffectType.MODIFY_HEALTH, max_val=self.get_max_health()
        )
        quest_holder = simple("quest", EffectType.MODIFY_QUEST)
        turn_holder = simple("remaining_turns", EffectType.MODIFY_TURNS)
        resource_draw_holder = const_val(
            "resources_draw", EffectType.MODIFY_RESOURCES, 0
        )
        resources_holder = dict_holder("resources", EffectType.MODIFY_RESOURCES)
        speed_holder = simple("speed", EffectType.MODIFY_SPEED)
        xp_holder = dict_holder("skill_xp", EffectType.MODIFY_XP)
        free_xp_holder = const_val("free_xp", EffectType.MODIFY_XP, 0)
        transport_val_holder = const_val("transport", EffectType.TRANSPORT, 0)
        job_val_holder = const_val("job", EffectType.DISRUPT_JOB, 0)

        add_emblem_outcomes: List[EncounterSingleOutcome[Optional[Emblem]]] = []
        for eff in effects_split.pop((EffectType.ADD_EMBLEM, False), []):
            old_idxs = [
                idx
                for idx in range(len(self.emblems))
                if self.emblems[idx].name == eff.param.name
            ]
            if old_idxs:
                old_emblem = self.emblems.pop(old_idxs[0])
                new_emblem = Emblem(
                    name=eff.param.name, feats=old_emblem.feats + eff.param.feats
                )
            else:
                old_emblem = None
                new_emblem = eff.param
            self.emblems.append(new_emblem)
            add_emblem_outcomes.append(
                EncounterSingleOutcome[Optional[Emblem]](
                    old_val=old_emblem, new_val=new_emblem, comments=[]
                )
            )

        if effects_split:
            raise Exception(f"Effects remaining unprocessed: {effects_split}")

        if reputation_holder.get_cur_value() < 0:
            job_val_holder.add(-1, "negative reputation")

        job_outcome: Optional[EncounterSingleOutcome[str]] = None
        if job_val_holder.get_cur_value() != 0:
            job_msg, new_job, is_promo = self._job_check(job_val_holder.get_cur_value())
            if new_job:
                old_job = self.job_name
                self.job_name = new_job
                self.tableau = []
                self.job_deck = []
                self.refill_tableau(board)
                # blow away earlier rep mods:
                reputation_holder.set_to(3, "set to 3 for job switch")
                if is_promo:
                    self._schedule_promotion(old_job)
                else:
                    # also move some (more)
                    transport_val_holder.add(3)
                job_outcome = EncounterSingleOutcome[str](
                    old_val=old_job, new_val=new_job, comments=[job_msg]
                )
            else:
                reputation_holder.add(-2, "-2 from job challenge: " + job_msg)

        resource_draws_outcome: Optional[EncounterSingleOutcome[int]] = None
        draw_cnt = resource_draw_holder.get_cur_value()
        if draw_cnt < 0:
            cur_rs = [nm for rs, cnt in self.resources.items() for nm in [rs] * cnt]
            to_rm = (
                random.sample(cur_rs, draw_cnt * -1)
                if len(cur_rs) > draw_cnt * -1
                else cur_rs
            )
            rcs = defaultdict(int)
            for rt in to_rm:
                rcs[rt] += 1
            for rt, cnt in rcs.items():
                resources_holder[rt].add(-cnt)
        elif draw_cnt > 0:
            loc = board.get_token_location(self.name)
            comments = []
            for _ in range(draw_cnt):
                draw = board.draw_resource_card(loc)
                if draw.value != 0:
                    resources_holder[draw.type].add(draw.value)
                comments.append(draw.name)
            resource_draws_outcome = EncounterSingleOutcome[int](
                old_val=0, new_val=draw_cnt, comments=comments
            )

        action_cnt = action_holder.get_cur_value()
        self.acted_this_turn = action_cnt <= 0

        free_xp = free_xp_holder.get_cur_value()
        if free_xp > 0:
            self._distribute_free_xp(free_xp)

        transport_outcome: Optional[EncounterSingleOutcome[str]] = None
        if transport_val_holder.get_cur_value() > 0:
            tp = transport_val_holder.get_cur_value()
            old_location = board.get_token_location(self.name)
            new_location = random.choice(
                board.find_hexes_near_token(self.name, tp - 2, tp + 2)
            )
            board.move_token(self.name, new_location)
            transport_outcome = EncounterSingleOutcome[str](
                old_val=old_location,
                new_val=new_location,
                comments=transport_val_holder._comments,
            )

        def dict_outcomes(dholder):
            return {
                k: v
                for k, v in [(ik, iv.to_outcome()) for ik, iv in dholder.items()]
                if v is not None
            }

        return EncounterOutcome(
            action_flag=action_holder.to_outcome(),
            coins=coins_holder.to_outcome(),
            reputation=reputation_holder.to_outcome(),
            xp=dict_outcomes(xp_holder),
            free_xp=free_xp_holder.to_outcome(),
            health=health_holder.to_outcome(),
            resource_draws=resource_draws_outcome,
            resources=dict_outcomes(resources_holder),
            quest=quest_holder.to_outcome(),
            turns=turn_holder.to_outcome(),
            speed=speed_holder.to_outcome(),
            transport_location=transport_outcome,
            new_job=job_outcome,
            emblems=add_emblem_outcomes,
        )

    def _schedule_promotion(self, job_name: str) -> None:
        job = load_job(job_name)
        deck = load_deck(job.deck_name)

        # first emblem is empty (+xp), then others give reliable feat
        emblem_effects = [[]]
        for sk in deck.base_skills:
            emblem_effects.append(
                [Feat(hook=HookType.RELIABLE_SKILL, param=sk, value=1)]
            )
        emblems = [
            Emblem(name=f"Veteran {job_name}", feats=ee) for ee in emblem_effects
        ]
        choice_list = [
            [Effect(type=EffectType.ADD_EMBLEM, param=e, value=1)] for e in emblems
        ]
        choice_list[0].append(Effect(type=EffectType.MODIFY_XP, param=None, value=10))

        promo_template = TemplateCard(
            copies=1,
            name="Job Promotion",
            desc=f"Select a benefit for being promoted from {job_name}.",
            unsigned=True,
            choices=Choices(
                min_choices=0,
                max_choices=1,
                is_random=False,
                choice_list=choice_list,
            ),
        )
        card = deck.make_card(
            promo_template,
            1,
            EncounterContextType.SYSTEM,
        )
        self.queue_encounter(card, context_type=EncounterContextType.SYSTEM)
        return True

    def _distribute_free_xp(self, xp: int) -> None:
        all_skills = load_skills()

        assign_template = TemplateCard(
            copies=1,
            name="Assign XP",
            desc=f"Assign {xp} xp",
            unsigned=True,
            choices=Choices(
                min_choices=0,
                max_choices=1,
                is_random=False,
                choice_list=[
                    [Effect(type=EffectType.MODIFY_XP, param=sk, value=xp)]
                    for sk in all_skills
                ],
            ),
        )

        custom_deck = load_deck("Custom")
        card = custom_deck.make_card(
            assign_template,
            1,
            EncounterContextType.SYSTEM,
        )
        self.queue_encounter(card, context_type=EncounterContextType.SYSTEM)
        return True

    def finish_turn(self, board: Board) -> None:
        if self._discard_resources():
            return

        self.remaining_turns -= 1
        self.acted_this_turn = False
        self.speed = self.get_init_speed()
        self.had_travel_encounter = False

        # filter to encounters near the PC (since they may have been transported, or just moved)
        near: Set[str] = {hx for hx in board.find_hexes_near_token(self.name, 0, 5)}

        def _is_valid(card: TableauCard) -> bool:
            return card.age > 1 and card.location in near

        self.tableau = [
            dataclasses.replace(c, age=c.age - 1) for c in self.tableau if _is_valid(c)
        ]
        self.refill_tableau(board)

    def _discard_resources(self) -> bool:
        # discard down to correct number of resources
        # (in the future should let player pick which to discard)
        all_rs = [nm for rs, cnt in self.resources.items() for nm in [rs] * cnt]
        overage = len(all_rs) - self.get_max_resources()
        if overage <= 0:
            return False

        discard_template = TemplateCard(
            copies=1,
            name="Discard Resources",
            desc=f"You must discard to {self.get_max_resources()} resources.",
            unsigned=True,
            choices=Choices(
                min_choices=overage,
                max_choices=overage,
                is_random=False,
                choice_list=[
                    [Effect(type=EffectType.MODIFY_RESOURCES, param=rs, value=-1)]
                    for rs in all_rs
                ],
            ),
        )

        custom_deck = load_deck("Custom")
        card = custom_deck.make_card(
            discard_template,
            1,
            EncounterContextType.SYSTEM,
        )
        self.queue_encounter(card, context_type=EncounterContextType.SYSTEM)
        return True

    def draw_travel_card(self, location: str, board: Board) -> Optional[FullCard]:
        if not self.travel_deck:
            self.travel_deck = self._make_travel_deck()

        card = self.travel_deck.pop(0)
        if card.type == TravelCardType.NOTHING:
            return None
        elif card.type == TravelCardType.DANGER:
            hx = board.get_hex(location)
            if hx.danger >= card.value:
                return board.draw_hex_card(location, EncounterContextType.TRAVEL)
            else:
                return None
        elif card.type == TravelCardType.TRINKET:
            trinket_template = TemplateCard(
                copies=1,
                name="A Find Along The Way",
                desc="...",
                choices=Choices(
                    min_choices=1,
                    max_choices=1,
                    is_random=True,
                    choice_list=[
                        [Effect(type=EffectType.MODIFY_COINS, value=1)],
                        [Effect(type=EffectType.MODIFY_COINS, value=6)],
                        [Effect(type=EffectType.MODIFY_RESOURCES, value=1)],
                        [Effect(type=EffectType.MODIFY_HEALTH, value=3)],
                        [Effect(type=EffectType.MODIFY_QUEST, value=1)],
                    ],
                ),
            )
            custom_deck = load_deck("Custom")
            return custom_deck.make_card(
                trinket_template, 1, EncounterContextType.TRAVEL
            )
        else:
            raise Exception(f"Unknown card type: {card.type}")

    def _make_travel_deck(self) -> List[TravelCard]:
        cards = (
            [TravelCard(type=TravelCardType.NOTHING)] * 14
            + [TravelCard(type=TravelCardType.DANGER, value=1)] * 2
            + [TravelCard(type=TravelCardType.DANGER, value=2)] * 2
            + [TravelCard(type=TravelCardType.DANGER, value=3)] * 2
            + [TravelCard(type=TravelCardType.DANGER, value=4)] * 2
            + [TravelCard(type=TravelCardType.DANGER, value=5)] * 2
            + [TravelCard(type=TravelCardType.TRINKET)] * 2
        )
        random.shuffle(cards)
        for _ in range((len(cards) // 10) + 1):
            cards.pop()
        return cards

    def draw_camp_card(self, board: Board) -> FullCard:
        if not self.camp_deck:
            template_deck = load_deck("Camp")
            additional: List[TemplateCard] = []
            job = load_job(self.job_name)
            self.camp_deck = template_deck.actualize(
                job.rank + 1, EncounterContextType.CAMP, additional
            )

        return self.camp_deck.pop(0)

    def _job_check(self, modifier: int) -> Tuple[str, Optional[str], bool]:
        target_number = 4 - modifier
        bonus = self.reputation // 4
        roll = random.randint(1, 8) + bonus
        jobs = load_jobs()
        next_job: Optional[str] = None
        is_promo = False
        if roll < target_number - 4:
            bad_jobs = [j for j in jobs if j.rank == 0]
            next_job = (random.choice(bad_jobs)).name
        elif roll < target_number:
            lower_jobs = [j for j in jobs if self.job_name in j.promotions]
            if lower_jobs:
                next_job = (random.choice(lower_jobs)).name
            else:
                bad_jobs = [j for j in jobs if j.rank == 0]
                next_job = (random.choice(bad_jobs)).name
        elif roll < target_number + 4:
            next_job = None
        else:
            cur_job = [j for j in jobs if j.name == self.job_name][0]
            promo_jobs = [j for j in jobs if j.name in cur_job.promotions]
            if promo_jobs:
                next_job = (random.choice(promo_jobs)).name
                is_promo = True
            else:
                next_job = None
        return (f"1d8+{bonus} vs {target_number}: {roll}", next_job, is_promo)


class CharacterStorage(ObjectStorageBase[Character]):
    TABLE_NAME = "character"
    TYPE = Character
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Character]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> Character:
        chars = cls._select_helper(["name = :name"], {"name": name})
        if not chars:
            raise IllegalMoveException(f"No such character: {name}")
        return chars[0]

    @classmethod
    def create(cls, character: Character) -> Character:
        cls._insert_helper([character])
        return character

    @classmethod
    def update(cls, character: Character) -> Character:
        cls._update_helper(character)
        return character
