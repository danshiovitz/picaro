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

from .board import load_board
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
    Action,
    Choices,
    Effect,
    EffectType,
    Emblem,
    Encounter,
    EncounterActions,
    EncounterContextType,
    EncounterEffect,
    Event,
    Feat,
    FullCard,
    HookType,
    JobType,
    Outcome,
    TableauCard,
    TemplateCard,
)


def clamp(val: int, min: Optional[int] = None, max: Optional[int] = None) -> int:
    if min is not None and val < min:
        return min
    elif max is not None and val > max:
        return max
    else:
        return val


class TurnFlags(Enum):
    ACTED = enum_auto()
    HAD_TRAVEL_ENCOUNTER = enum_auto()
    BAD_REP_CHECKED = enum_auto()


class TravelCardType(Enum):
    NOTHING = enum_auto()
    DANGER = enum_auto()
    TRINKET = enum_auto()


@dataclass
class TravelCard:
    type: TravelCardType
    value: int = 0


class Character:
    @classmethod
    def create(cls, name: str, player_id: int, job_name: str, location: str) -> None:
        data = CharacterData(
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
            speed=0,
            turn_flags=set(),
        )

        ch = Character(name)
        ch.data = data
        data.health = ch._get_max_health()
        data.speed = ch._get_init_speed()
        data.remaining_turns = ch._get_init_turns()
        data.luck = ch._get_max_luck()
        CharacterStorage.create(data)

        board = load_board()
        board.add_token(
            name=name, type="Character", location=location, actions=None, events=[]
        )

    @classmethod
    def load(cls, character_name: str) -> "Character":
        return Character(character_name)

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "Character":
        self.data = CharacterStorage.load_by_name(self.name)
        return self

    def __exit__(self, *exc: Any) -> None:
        CharacterStorage.update(self.data)

    def has_encounters(self) -> bool:
        return self.data.encounters

    def check_set_flag(self, flag: TurnFlags) -> bool:
        prev = flag in self.data.turn_flags
        self.data.turn_flags.add(flag)
        return not prev

    def acted_this_turn(self) -> None:
        return TurnFlags.ACTED in self.data.turn_flags

    def get_speed(self) -> int:
        return self.data.speed

    def get_reputation(self) -> int:
        return self.data.reputation

    def get_resources(self) -> Dict[str, int]:
        return self.data.resources.copy()

    def get_max_resources(self) -> int:
        return self._get_max_resources()

    def get_snapshot(self) -> snapshot_Character:
        all_skills = load_skills()
        board = load_board()
        location = board.get_token_location(self.name)
        routes = board.best_routes(location, [c.location for c in self.data.tableau])
        return snapshot_Character(
            name=self.data.name,
            player_id=self.data.player_id,
            skills={sk: self._get_skill_rank(sk) for sk in all_skills},
            skill_xp={sk: self.data.skill_xp.get(sk, 0) for sk in all_skills},
            job=self.data.job_name,
            health=self.data.health,
            max_health=self._get_max_health(),
            coins=self.data.coins,
            resources=self.data.resources,
            max_resources=self._get_max_resources(),
            reputation=self.data.reputation,
            quest=self.data.quest,
            location=location,
            remaining_turns=self.data.remaining_turns,
            acted_this_turn=self.acted_this_turn(),
            luck=self.data.luck,
            speed=self.data.speed,
            max_speed=self._get_init_speed(),
            tableau=tuple(
                self._tableau_snapshot(c, routes[c.location]) for c in self.data.tableau
            ),
            encounters=tuple(self._encounter_snapshot(e) for e in self.data.encounters),
            emblems=tuple(self.data.emblems),
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

    def queue_tableau_card(self, card_id: str) -> None:
        card = self._remove_tableau_card(card_id)
        board = load_board()
        location = board.get_token_location(self.data.name)
        if card.location != location:
            raise IllegalMoveException(
                f"You must be in hex {card.location} for that encounter."
            )
        self._queue_encounter(card.card, context_type=EncounterContextType.JOB)

    def queue_template(
        self, template: TemplateCard, context_type: EncounterContextType
    ) -> None:
        custom_deck = load_deck("Custom")
        card = custom_deck.make_card(template, 1, context_type)
        self._queue_encounter(card, context_type=context_type)

    def queue_camp_card(self) -> None:
        card = self._draw_camp_card()
        self._queue_encounter(card, context_type=EncounterContextType.CAMP)

    def queue_travel_card(self, location) -> None:
        if TurnFlags.HAD_TRAVEL_ENCOUNTER not in self.data.turn_flags:
            card = self._draw_travel_card(location)
            if card:
                self._queue_encounter(card, context_type=EncounterContextType.TRAVEL)
                self.data.turn_flags.add(TurnFlags.HAD_TRAVEL_ENCOUNTER)

    def step(self, location: str, events: List[Event]) -> None:
        if self.data.speed < 1:
            raise IllegalMoveException(f"You don't have enough speed.")

        # moving and decreasing speed are normal effects, so we don't report them
        # in events (this might be wrong, especially if we eventually want events
        # to be a true undo log, but it makes the client easier for now)
        self.data.speed -= 1
        board = load_board()
        board.move_token(
            self.data.name, location, adjacent=True, comments=["Travel"], events=[]
        )

    def refill_tableau(self) -> None:
        job = load_job(self.data.job_name)
        while len(self.data.tableau) < self._get_max_tableau_size():
            if not self.data.job_deck:
                additional: List[TemplateCard] = []
                self.data.job_deck = job.make_deck(additional=additional)
            card = self.data.job_deck.pop(0)
            dst = random.choice(job.encounter_distances)
            board = load_board()
            location = random.choice(
                board.find_hexes_near_token(self.data.name, dst, dst)
            )

            self.data.tableau.append(
                TableauCard(card=card, location=location, age=self._get_init_card_age())
            )

    def pop_encounter(self) -> Encounter:
        if not self.data.encounters:
            raise BadStateException("There is no active encounter.")

        return self.data.encounters.pop(0)

    def turn_reset(self) -> None:
        # these are all expected, so not reporting them in events
        self.data.remaining_turns -= 1
        self.data.turn_flags.clear()
        self.data.speed = self._get_init_speed()

    def age_tableau(self, near: Set[str]) -> None:
        def is_valid(card: TableauCard) -> bool:
            return card.age > 1 and card.location in near

        self.data.tableau = [
            dataclasses.replace(c, age=c.age - 1)
            for c in self.data.tableau
            if is_valid(c)
        ]

    def _get_init_turns(self) -> int:
        return clamp(20 + self._calc_hook(HookType.INIT_TURNS), min=10, max=40)

    def _get_max_luck(self) -> int:
        return clamp(5 + self._calc_hook(HookType.MAX_LUCK), min=0)

    def _get_max_tableau_size(self) -> int:
        return clamp(3 + self._calc_hook(HookType.MAX_TABLEAU_SIZE), min=1)

    def _get_init_card_age(self) -> int:
        return clamp(3 + self._calc_hook(HookType.INIT_CARD_AGE), min=1)

    def _get_max_health(self) -> int:
        return clamp(20 + self._calc_hook(HookType.MAX_HEALTH), min=1)

    def _get_max_resources(self) -> int:
        job = load_job(self.data.job_name)
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

    def _get_skill_rank(self, skill_name: str) -> int:
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        xp = self.data.skill_xp.get(skill_name, 0)
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

    def _get_init_speed(self) -> int:
        job = load_job(self.data.job_name)
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

    def _calc_hook(
        self, hook_name: HookType, hook_subtype: Optional[str] = None
    ) -> int:
        tot = 0
        for emblem in self.data.emblems:
            for feat in emblem.feats:
                if feat.hook == hook_name:
                    subtype_match = (
                        hook_subtype is None
                        or feat.subtype is None
                        or hook_subtype == feat.subtype
                    )
                    if subtype_match:
                        tot += feat.value
        return tot

    def _remove_tableau_card(self, card_id: str) -> TableauCard:
        idx = [
            i
            for i in range(len(self.data.tableau))
            if self.data.tableau[i].card.id == card_id
        ]
        if not idx:
            raise BadStateException(f"No such encounter card found ({card_id})")
        return self.data.tableau.pop(idx[0])

    def _queue_encounter(
        self, card: FullCard, context_type: EncounterContextType
    ) -> None:
        rolls = []
        for chk in card.checks:
            bonus = self._get_skill_rank(chk.skill)
            roll_min = 0 + self._calc_hook(HookType.RELIABLE_SKILL, chk.skill)
            roll_val = clamp(random.randint(1, 8), min=roll_min, max=None)
            rolls.append(roll_val + bonus)
        if card.choices and card.choices.is_random:
            rolls.extend(
                random.randint(1, len(card.choices.choice_list))
                for _ in range(card.choices.max_choices)
            )
        self.data.encounters.append(
            Encounter(
                card=card,
                rolls=rolls,
                context_type=context_type,
            )
        )

    def _schedule_promotion(self, job_name: str) -> None:
        job = load_job(job_name)
        deck = load_deck(job.deck_name)

        # first emblem is empty (+xp), then others give reliable feat
        emblem_effects = [[]]
        for sk in deck.base_skills:
            emblem_effects.append(
                [Feat(hook=HookType.RELIABLE_SKILL, subtype=sk, value=1)]
            )
        emblems = [
            Emblem(name=f"Veteran {job_name}", feats=ee) for ee in emblem_effects
        ]
        extra = [[] for ee in emblems]
        extra[0].append(Effect(type=EffectType.MODIFY_XP, subtype=None, value=10))
        choice_list = [
            Choice(benefit=tuple([Effect(type=EffectType.ADD_EMBLEM, value=e)] + xt))
            for e, xt in zip(emblems, extra)
        ]

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
        self._queue_template(promo_template, context_type=EncounterContextType.SYSTEM)

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
                    Choice(
                        benefit=(
                            Effect(type=EffectType.MODIFY_XP, subtype=sk, value=xp),
                        )
                    )
                    for sk in all_skills
                ],
            ),
        )
        self._queue_template(assign_template, context_type=EncounterContextType.SYSTEM)

    def _draw_travel_card(self, location: str) -> Optional[FullCard]:
        if not self.data.travel_deck:
            self.data.travel_deck = self._make_travel_deck()

        card = self.data.travel_deck.pop(0)
        if card.type == TravelCardType.NOTHING:
            return None
        elif card.type == TravelCardType.DANGER:
            board = load_board()
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
                        Choice(
                            benefit=(Effect(type=EffectType.MODIFY_COINS, value=1),)
                        ),
                        Choice(
                            benefit=(Effect(type=EffectType.MODIFY_COINS, value=6),)
                        ),
                        Choice(
                            benefit=(Effect(type=EffectType.MODIFY_RESOURCES, value=1),)
                        ),
                        Choice(
                            benefit=(Effect(type=EffectType.MODIFY_HEALTH, value=3),)
                        ),
                        Choice(
                            benefit=(Effect(type=EffectType.MODIFY_QUEST, value=1),)
                        ),
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

    def _draw_camp_card(self) -> FullCard:
        if not self.data.camp_deck:
            template_deck = load_deck("Camp")
            additional: List[TemplateCard] = []
            job = load_job(self.job_name)
            self.data.camp_deck = template_deck.actualize(
                job.rank + 1, EncounterContextType.CAMP, additional
            )

        return self.data.camp_deck.pop(0)

    def _job_check(self, modifier: int) -> Tuple[str, Optional[str], bool]:
        target_number = 4 - modifier
        bonus = self.data.reputation // 4
        roll = random.randint(1, 8) + bonus
        jobs = load_jobs()
        next_job: Optional[str] = None
        is_promo = False
        if roll < target_number - 4:
            bad_jobs = [j for j in jobs if j.rank == 0]
            next_job = (random.choice(bad_jobs)).name
        elif roll < target_number:
            lower_jobs = [j for j in jobs if self.data.job_name in j.promotions]
            if lower_jobs:
                next_job = (random.choice(lower_jobs)).name
            else:
                bad_jobs = [j for j in jobs if j.rank == 0]
                next_job = (random.choice(bad_jobs)).name
        elif roll < target_number + 4:
            next_job = None
        else:
            cur_job = [j for j in jobs if j.name == self.data.job_name][0]
            promo_jobs = [j for j in jobs if j.name in cur_job.promotions]
            if promo_jobs:
                next_job = (random.choice(promo_jobs)).name
                is_promo = True
            else:
                next_job = None
        return (f"1d8+{bonus} vs {target_number}: {roll}", next_job, is_promo)

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
                            subtype=encounter.card.checks[0].skill,
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
                        subtype=encounter.card.checks[0].skill,
                        value=failures,
                    )
                )

        for c in actions.choices:
            choice = encounter.card.choices.choice_list[c]
            ret.extend(choice.benefit)
            ret.extend(dataclasses.replace(ct, is_cost=True) for ct in choice.cost)

        return ret

    # note this does update luck as well as validating stuff
    def _validate_actions(
        self, encounter: Encounter, actions: EncounterActions
    ) -> None:
        if encounter.card.checks:
            # validate the actions by rerunning them
            luck = self.data.luck
            rolls = list(encounter.rolls[:])

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

            self.data.luck = luck

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
        events: List[Event],
    ) -> None:
        # want something like: first process gain coins, if any, then process lose coins, if any,
        # then gain resources, then lose resources, ... , then job change, then pick the actual
        # transport location if any
        # we do it this way because we want, eg, to be able to overwrite reputation changes with
        # reputation set via job change (note that any 'set' overwrites previous comments, as well)
        effects_split = defaultdict(list)
        for effect in effects:
            effects_split[(effect.type, effect.subtype is None)].append(effect)

        def simple(
            name: str, effect_type: EffectType, max_val: Optional[int] = None
        ) -> UpdateHolder:
            get_f = lambda: getattr(self.data, name)

            def set_f(old_val, new_val, comments) -> None:
                setattr(self.data, name, new_val)
                events.append(
                    Event.for_character(
                        self.name, effect_type, None, old_val, new_val, comments
                    )
                )

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
            char_self = self.data

            class HolderDict(dict):
                def __missing__(self, subtype):
                    get_f = lambda: getattr(char_self, name).get(subtype, 0)

                    def set_f(old_val, new_val, comments) -> None:
                        getattr(char_self, name)[subtype] = new_val
                        events.append(
                            Event.for_character(
                                char_self.name,
                                effect_type,
                                subtype,
                                old_val,
                                new_val,
                                comments,
                            )
                        )

                    holder = UpdateHolder(
                        name,
                        effect_type,
                        subtype,
                        context_type,
                        0,
                        None,
                        get_f=get_f,
                        set_f=set_f,
                    )
                    self[subtype] = holder
                    return holder

            subtypes = {
                e.subtype for e in effects if e.type == effect_type and e.subtype
            }
            ret = HolderDict()
            for subtype in subtypes:
                ret[subtype].apply_effects(effects_split.pop((effect_type, False), []))
            return ret

        def const_val(
            name: str, effect_type: EffectType, init_val: int
        ) -> UpdateHolder:
            get_f = lambda: init_val
            set_f = lambda _old_val, _new_val, _comments: None
            holder = UpdateHolder(
                name, effect_type, None, context_type, 0, None, get_f=get_f, set_f=set_f
            )
            holder.apply_effects(effects_split.pop((effect_type, True), []))
            return holder

        action_holder = const_val(
            "action_flag",
            EffectType.MODIFY_ACTION,
            0 if TurnFlags.ACTED in self.data.turn_flags else 1,
        )
        coins_holder = simple("coins", EffectType.MODIFY_COINS)
        reputation_holder = simple("reputation", EffectType.MODIFY_REPUTATION)
        health_holder = simple(
            "health", EffectType.MODIFY_HEALTH, max_val=self._get_max_health()
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
        job_val_holder = const_val("job", EffectType.DISRUPT_JOB, 0)

        for eff in effects_split.pop((EffectType.ADD_EMBLEM, False), []):
            old_idxs = [
                idx
                for idx in range(len(self.data.emblems))
                if self.data.emblems[idx].name == eff.value.name
            ]
            if old_idxs:
                old_emblem = self.data.emblems.pop(old_idxs[0])
                new_emblem = Emblem(
                    name=eff.value.name, feats=old_emblem.feats + eff.value.feats
                )
            else:
                old_emblem = None
                new_emblem = eff.value
            self.data.emblems.append(new_emblem)
            events.append(
                Event.for_character(
                    self.data.name,
                    EffectType.ADD_EMBLEM,
                    None,
                    old_emblem,
                    new_emblem,
                    [],
                )
            )

        if job_val_holder.get_cur_value() != 0:
            job_msg, new_job, is_promo = self._job_check(job_val_holder.get_cur_value())
            if new_job:
                old_job = self.data.job_name
                self.data.job_name = new_job
                self.data.tableau = []
                self.data.job_deck = []
                self._refill_tableau()
                # blow away earlier rep mods:
                reputation_holder.set_to(3, "set to 3 for job switch")
                if is_promo:
                    self._schedule_promotion(old_job)
                else:
                    # also move some (more)
                    move_eff = Effect(
                        type=EffectType.TRANSPORT, value=3, subtype=None, is_cost=False
                    )
                    effects_split[(move_eff.type, move_eff.subtype is None)].append(
                        move_eff
                    )
                events.append(
                    Event.for_character(
                        self.data.name,
                        EffectType.MODIFY_JOB,
                        None,
                        old_job,
                        new_job,
                        [job_msg],
                    )
                )
            else:
                reputation_holder.add(-2, "-2 from job challenge: " + job_msg)

        board = load_board()

        draw_cnt = resource_draw_holder.get_cur_value()
        if draw_cnt < 0:
            cur_rs = [
                nm for rs, cnt in self.data.resources.items() for nm in [rs] * cnt
            ]
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
            events.append(
                Event.for_character(
                    self.name, EffectType.MODIFY_RESOURCES, None, 0, draw_cnt, comments
                )
            )

        action_cnt = action_holder.get_cur_value()
        if action_cnt <= 0:
            self.data.turn_flags.add(TurnFlags.ACTED)
        else:
            self.data.turn_flags.discard(TurnFlags.ACTED)

        free_xp = free_xp_holder.get_cur_value()
        if free_xp > 0:
            self._distribute_free_xp(free_xp)

        for eff in effects_split.pop((EffectType.TRANSPORT, True), []):
            tp_mod = eff.value // 5 + 1
            tp_min = clamp(eff.value - tp_mod, min=1)
            tp_max = eff.value + tp_mod
            old_location = board.get_token_location(self.name)
            new_location = random.choice(
                board.find_hexes_near_token(self.name, tp_min, tp_max)
            )
            board.move_token(
                self.name,
                new_location,
                adjacent=False,
                comments=[f"random {tp_min}-{tp_max} hex transport"],
                events=events,
            )

        for eff in effects_split.pop((EffectType.MODIFY_LOCATION, False), []):
            board.move_token(
                self.name, eff.value, adjacent=False, comments=[], events=events
            )

        if effects_split:
            raise Exception(f"Effects remaining unprocessed: {effects_split}")

        action_holder.write(events)
        coins_holder.write(events)
        reputation_holder.write(events)
        for v in xp_holder.values():
            v.write(events)
        free_xp_holder.write(events)
        health_holder.write(events)
        for v in resources_holder.values():
            v.write(events)
        quest_holder.write(events)
        turn_holder.write(events)
        speed_holder.write(events)


# This class is not frozen, and also not exposed externally - it needs to be loaded every time
# it's used and saved at the end
@dataclass
class CharacterData:
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
    speed: int
    turn_flags: Set[TurnFlags]


class CharacterStorage(ObjectStorageBase[CharacterData]):
    TABLE_NAME = "character"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[CharacterData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> CharacterData:
        chars = cls._select_helper(["name = :name"], {"name": name})
        if not chars:
            raise IllegalMoveException(f"No such character: {name}")
        return chars[0]

    @classmethod
    def create(cls, character: CharacterData) -> CharacterData:
        cls._insert_helper([character])
        return character

    @classmethod
    def update(cls, character: CharacterData) -> CharacterData:
        cls._update_helper(character)
        return character
