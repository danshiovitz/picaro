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
    cast,
)

from picaro.common.utils import clamp

from .board import load_board
from .deck import actualize_deck, load_deck, make_card
from .entity import (
    Entity,
    EntityField,
    IntEntityField,
    SimpleIntEntityField,
    SimpleDictIntEntityField,
)
from .exceptions import BadStateException, IllegalMoveException
from .game import load_game
from .job import Job, load_job, load_jobs
from .project import (
    Task,
    TaskExtraResource,
    TaskStatus,
    TaskType,
)
from .snapshot import (
    Character as snapshot_Character,
    Encounter as snapshot_Encounter,
    TableauCard as snapshot_TableauCard,
    EncounterType as snapshot_EncounterType,
)
from .storage import ObjectStorageBase, ReadOnlyWrapper
from .types import (
    Action,
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterActions,
    EncounterContextType,
    EncounterEffect,
    EntityType,
    FullCard,
    FullCardType,
    Gadget,
    Record,
    Rule,
    RuleType,
    JobType,
    Outcome,
    TableauCard,
    TemplateCard,
    TemplateCardType,
    make_id,
)


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


class Character(Entity, ReadOnlyWrapper):
    ENTITY_TYPE = EntityType.CHARACTER
    FIELDS = [
        lambda _vs: [LeadershipMetaField()],
        lambda _vs: [ModifyJobField()],
        lambda _vs: [ResourceDrawMetaField()],
        lambda recs: SimpleDictIntEntityField.make_fields(
            recs, "resources", "resources", EffectType.MODIFY_RESOURCES
        ),
        lambda _vs: [TransportField()],
        lambda _vs: [ModifyLocationField()],
        lambda _vs: [ModifyActivityField()],
        lambda _vs: [AddEmblemField()],
        lambda _vs: [QueueEncounterField()],
        lambda _vs: [SimpleIntEntityField("coins", "coins", EffectType.MODIFY_COINS)],
        lambda _vs: [
            SimpleIntEntityField(
                "reputation", "reputation", EffectType.MODIFY_REPUTATION
            )
        ],
        lambda _vs: [
            SimpleIntEntityField(
                "health",
                "health",
                EffectType.MODIFY_HEALTH,
                max_value=lambda e: e.get_max_health(),
            )
        ],
        lambda _vs: [
            SimpleIntEntityField("turns", "remaining_turns", EffectType.MODIFY_TURNS)
        ],
        # speed gets reset to its max each turn, but we allow it to go over
        # within a turn
        lambda _vs: [SimpleIntEntityField("speed", "speed", EffectType.MODIFY_SPEED)],
        lambda recs: SimpleDictIntEntityField.make_fields(
            recs, "xp", "skill_xp", EffectType.MODIFY_XP
        ),
        lambda _vs: [ModifyFreeXpField()],
    ]

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
            remaining_turns=0,
            luck=0,
            emblems=[],
            tableau=[],
            encounter=None,
            queued=[],
            job_deck=[],
            travel_deck=[],
            camp_deck=[],
            speed=0,
            turn_flags=set(),
        )

        ch = Character(data)
        data.health = ch.get_max_health()
        data.speed = ch.get_init_speed()
        data.remaining_turns = ch.get_init_turns()
        data.luck = ch.get_max_luck()
        CharacterStorage.create(data)

        board = load_board()
        board.add_token(
            name=name,
            type=EntityType.CHARACTER,
            location=location,
            actions=None,
            records=[],
        )

    @classmethod
    def load(cls, character_name: str) -> "CharacterContext":
        return CharacterContext(character_name)

    def check_set_flag(self, flag: TurnFlags) -> bool:
        prev = flag in self._data.turn_flags
        self._data.turn_flags.add(flag)
        return not prev

    def acted_this_turn(self) -> None:
        return TurnFlags.ACTED in self._data.turn_flags

    def has_encounters(self) -> None:
        return self.encounter or self.queued

    def get_snapshot(self) -> snapshot_Character:
        all_skills = load_game().skills
        board = load_board()
        location = board.get_token_location(self.name)
        routes = board.best_routes(location, [c.location for c in self._data.tableau])
        with Task.load_for_character(self.name) as raw_tasks:
            tasks = [t.get_snapshot() for t in raw_tasks]

        return snapshot_Character(
            name=self._data.name,
            player_id=self._data.player_id,
            skills={sk: self.get_skill_rank(sk) for sk in all_skills},
            skill_xp={sk: self._data.skill_xp.get(sk, 0) for sk in all_skills},
            job=self._data.job_name,
            health=self._data.health,
            max_health=self.get_max_health(),
            coins=self._data.coins,
            resources=self._data.resources,
            max_resources=self.get_max_resources(),
            reputation=self._data.reputation,
            location=location,
            remaining_turns=self._data.remaining_turns,
            acted_this_turn=self.acted_this_turn(),
            luck=self._data.luck,
            speed=self._data.speed,
            max_speed=self.get_init_speed(),
            tableau=tuple(
                self._tableau_snapshot(c, routes[c.location])
                for c in self._data.tableau
            ),
            encounter=self._encounter_snapshot(self._data.encounter)
            if self._data.encounter
            else None,
            queued=tuple(self._data.queued),
            emblems=tuple(self._data.emblems),
            tasks=tuple(tasks),
        )

    def _tableau_snapshot(
        self, card: TableauCard, route: Sequence[str]
    ) -> Sequence[snapshot_TableauCard]:
        if card.card.type == FullCardType.CHALLENGE:
            # in the future might be able to preview more checks so leaving them as lists
            data = card.card.data[0:1]
        elif card.card.type == FullCardType.CHOICE:
            data = "choice"
        elif card.card.type == FullCardType.SPECIAL:
            data = card.card.data

        return snapshot_TableauCard(
            id=card.card.id,
            name=card.card.name,
            type=card.card.type,
            data=data,
            age=card.age,
            location=card.location,
            route=tuple(route),
            is_extra=card.is_extra,
        )

    def _encounter_snapshot(self, encounter: Encounter) -> Sequence[snapshot_Encounter]:
        card_type = (
            snapshot_EncounterType.CHALLENGE
            if encounter.card.type == FullCardType.CHALLENGE
            else snapshot_EncounterType.CHOICE
        )
        return snapshot_Encounter(
            name=encounter.card.name,
            desc=encounter.card.desc,
            type=card_type,
            data=encounter.card.data,
            signs=encounter.card.signs,
            rolls=encounter.rolls,
        )

    def queue_tableau_card(self, card_id: str) -> None:
        card = self._remove_tableau_card(card_id)
        board = load_board()
        location = board.get_token_location(self._data.name)
        if card.location != location:
            raise IllegalMoveException(
                f"You must be in hex {card.location} for that encounter."
            )
        self._queue_encounter(card.card)

    def queue_template(
        self, template: TemplateCard, context_type: EncounterContextType
    ) -> None:
        card = make_card(None, template, 1, context_type)
        self._queue_encounter(card)

    def queue_camp_card(self) -> None:
        card = self._draw_camp_card()
        self._queue_encounter(card)

    def queue_travel_card(self, location) -> None:
        if TurnFlags.HAD_TRAVEL_ENCOUNTER not in self._data.turn_flags:
            card = self._draw_travel_card(location)
            if card:
                self._queue_encounter(card)
                self._data.turn_flags.add(TurnFlags.HAD_TRAVEL_ENCOUNTER)

    def step(self, location: str, records: List[Record]) -> None:
        if self._data.speed < 1:
            raise IllegalMoveException(f"You don't have enough speed.")

        # moving and decreasing speed are normal effects, so we don't report them
        # in records (this might be wrong, especially if we eventually want records
        # to be a true undo log, but it makes the client easier for now)
        self._data.speed -= 1
        board = load_board()
        board.move_token(
            self._data.name, location, adjacent=True, comments=["Travel"], records=[]
        )

    def refill_tableau(self) -> None:
        job = load_job(self._data.job_name)
        while (
            sum(1 for c in self._data.tableau if not c.is_extra)
            < self.get_max_tableau_size()
        ):
            if not self._data.job_deck:
                additional: List[TemplateCard] = []
                with Task.load_for_character(self.name) as tasks:
                    for task in tasks:
                        additional.extend(task.get_templates())
                self._data.job_deck = self._make_job_deck(job, additional=additional)
            card = self._data.job_deck.pop(0)
            dst = random.choice(job.encounter_distances)
            board = load_board()
            location = random.choice(
                board.find_hexes_near_token(self._data.name, dst, dst)
            )

            self._data.tableau.append(
                TableauCard(
                    card=card,
                    location=location,
                    age=self.get_init_tableau_age(),
                    is_extra=False,
                )
            )

    def add_extra_to_tableau(
        self, template_card: TemplateCard, location: str, age: int
    ) -> None:
        job = load_job(self._data.job_name)
        full_card = self._make_single_job_card(job, template_card)
        self._data.tableau.append(
            TableauCard(card=full_card, location=location, age=age, is_extra=True)
        )

    def encounter_finished(self) -> None:
        if self._data.queued:
            card = self._data.queued.pop(0)
            self._data.encounter = self._make_encounter(card)
        else:
            self._data.encounter = None

    def _queue_encounter(self, card: FullCard) -> None:
        if self._data.encounter:
            self._data.queued.append(card)
        else:
            self._data.encounter = self._make_encounter(card)

    def _make_encounter(self, card: FullCard) -> Encounter:
        if card.type == FullCardType.SPECIAL:
            card = self._actualize_special_card(card)

        rolls = []
        if card.type == FullCardType.CHALLENGE:
            for chk in card.data:
                bonus = self.get_skill_rank(chk.skill)
                roll_val = random.randint(1, 8)
                if roll_val <= self._calc_rule(RuleType.RELIABLE_SKILL, chk.skill):
                    roll_val = random.randint(1, 8)
                rolls.append(roll_val + bonus)
        elif card.type == FullCardType.CHOICE:
            if card.data.is_random:
                rolls.extend(
                    random.randint(1, len(card.data.choice_list))
                    for _ in range(card.data.max_choices)
                )
        else:
            raise Exception(f"Unknown card type: {card.type.name}")

        return Encounter(
            card=card,
            rolls=rolls,
        )

    def _actualize_special_card(
        self,
        card: FullCard,
    ) -> FullCard:
        special_type = card.data
        if special_type == "trade":
            all_resources = load_game().resources
            card_type = FullCardType.CHOICE
            data = Choices(
                min_choices=0,
                max_choices=sum(self.resources.values()),
                is_random=False,
                choice_list=[
                    Choice(
                        cost=[
                            Effect(
                                type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1
                            )
                        ],
                        benefit=[
                            Effect(
                                type=EffectType.MODIFY_COINS,
                                value=5,
                            )
                        ],
                        max_choices=self.resources[rs],
                    )
                    for rs in all_resources
                    if self.resources.get(rs, 0) > 0
                ],
                cost=[Effect(type=EffectType.MODIFY_ACTIVITY, value=-1)],
            )
        elif special_type == "deliver":
            card_type = FullCardType.CHOICE
            task_rs: List[Tuple[str, str]] = []
            with Task.load_for_character(self.name) as tasks:
                for task in tasks:
                    if (
                        task.project_name != card.entity_name
                        or task.type != TaskType.RESOURCE
                        or task.status != TaskStatus.IN_PROGRESS
                    ):
                        continue
                    extra = cast(TaskExtraResource, task.extra)
                    task_rs.extend((task.name, rs) for rs in extra.wanted_resources)
            data = Choices(
                min_choices=0,
                max_choices=99,
                is_random=False,
                choice_list=[
                    Choice(
                        cost=[
                            Effect(
                                type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1
                            )
                        ],
                        benefit=[
                            Effect(
                                entity_type=EntityType.TASK,
                                entity_name=task_name,
                                type=EffectType.MODIFY_RESOURCES,
                                subtype=rs,
                                value=1,
                            )
                        ],
                        max_choices=self.resources.get(rs, 0),
                    )
                    for task_name, rs in task_rs
                ],
                cost=[Effect(type=EffectType.MODIFY_ACTIVITY, value=-1)],
            )
        else:
            raise Exception(f"Unknown special type: {special_type}")
        return dataclasses.replace(card, type=card_type, data=data)

    def discard_job_card(self, num_cards: int) -> None:
        if num_cards <= 0:
            return
        self._data.job_deck = self._data.job_deck[num_cards:]

    def turn_reset(self) -> None:
        # these are all expected, so not reporting them in records
        self._data.remaining_turns -= 1
        self._data.turn_flags.clear()
        self._data.speed = self.get_init_speed()

    def age_tableau(self, near: Set[str]) -> None:
        def is_valid(card: TableauCard) -> bool:
            return card.age > 1 and (card.location in near or card.is_extra)

        self._data.tableau = [
            dataclasses.replace(c, age=c.age - 1)
            for c in self._data.tableau
            if is_valid(c)
        ]

    def spend_luck(self, amt: int, action: str) -> None:
        if self._data.luck < amt:
            raise BadStateException(f"Luck too low for {action}")
        self._data.luck -= amt

    def get_init_turns(self) -> int:
        return clamp(20 + self._calc_rule(RuleType.INIT_TURNS), min=10, max=40)

    def get_max_luck(self) -> int:
        return clamp(5 + self._calc_rule(RuleType.MAX_LUCK), min=0)

    def get_max_tableau_size(self) -> int:
        return clamp(3 + self._calc_rule(RuleType.MAX_TABLEAU_SIZE), min=1)

    def get_init_tableau_age(self) -> int:
        return clamp(3 + self._calc_rule(RuleType.INIT_TABLEAU_AGE), min=1)

    def get_max_health(self) -> int:
        return clamp(20 + self._calc_rule(RuleType.MAX_HEALTH), min=1)

    def get_max_resources(self) -> int:
        job = load_job(self._data.job_name)
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
        return clamp(base_limit + self._calc_rule(RuleType.MAX_RESOURCES), min=0)

    def get_max_tasks(self) -> int:
        return 3

    def get_max_oracles(self) -> int:
        return 3

    def get_skill_rank(self, skill_name: str) -> int:
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        xp = self._data.skill_xp.get(skill_name, 0)
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
            base_rank + self._calc_rule(RuleType.SKILL_RANK, skill_name), min=0, max=6
        )

    def get_init_speed(self) -> int:
        job = load_job(self._data.job_name)
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
        return clamp(base_speed + self._calc_rule(RuleType.INIT_SPEED), min=0)

    def _calc_rule(
        self, rule_type: RuleType, rule_subtype: Optional[str] = None
    ) -> int:
        tot = 0
        for emblem in self._data.emblems:
            for rule in emblem.rules:
                if rule.type == rule_type:
                    subtype_match = (
                        rule_subtype is None
                        or rule.subtype is None
                        or rule_subtype == rule.subtype
                    )
                    if subtype_match:
                        tot += rule.value
        return tot

    def _make_job_deck(
        self, job: Job, additional: List[TemplateCard] = None
    ) -> List[FullCard]:
        # template_deck = load_deck(job.deck_name)
        template_deck = load_deck("Raider")
        return actualize_deck(
            template_deck, job.rank + 1, EncounterContextType.JOB, additional
        )

    def _make_single_job_card(self, job: Job, single: TemplateCard) -> FullCard:
        # template_deck = load_deck(job.deck_name)
        template_deck = load_deck("Raider")
        return make_card(template_deck, single, job.rank + 1, EncounterContextType.JOB)

    def _remove_tableau_card(self, card_id: str) -> TableauCard:
        idx = [
            i
            for i in range(len(self._data.tableau))
            if self._data.tableau[i].card.id == card_id
        ]
        if not idx:
            raise BadStateException(f"No such encounter card found ({card_id})")
        return self._data.tableau.pop(idx[0])

    def _schedule_promotion(self, job_name: str) -> None:
        job = load_job(job_name)
        deck = load_deck(job.deck_name)

        # first emblem is empty (+xp), then others give reliable rule
        emblem_effects = [[]]
        for sk in deck.base_skills:
            emblem_effects.append(
                [
                    Rule(
                        type=RuleType.RELIABLE_SKILL,
                        subtype=sk,
                        value=1,
                    )
                ],
            )
        emblems = [
            Gadget(name=f"Veteran {job_name}", desc=None, rules=ee) for ee in emblem_effects
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
        self.queue_template(promo_template, context_type=EncounterContextType.SYSTEM)

    def _distribute_free_xp(self, xp: int) -> None:
        all_skills = load_game().skills

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
        self.queue_template(assign_template, context_type=EncounterContextType.SYSTEM)

    def _draw_travel_card(self, location: str) -> Optional[FullCard]:
        if not self._data.travel_deck:
            self._data.travel_deck = self._make_travel_deck()

        card = self._data.travel_deck.pop(0)
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
                type=TemplateCardType.CHOICE,
                data=Choices(
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
                            benefit=(Effect(type=EffectType.MODIFY_SPEED, value=2),)
                        ),
                    ],
                ),
            )
            return make_card(None, trinket_template, 1, EncounterContextType.TRAVEL)
        else:
            raise Exception(f"Unknown card type: {card.type}")

    def _make_travel_deck(self) -> List[TravelCard]:
        cards = (
            [TravelCard(type=TravelCardType.NOTHING)] * 14
            + [TravelCard(type=TravelCardType.DANGER, value=1)] * 3
            + [TravelCard(type=TravelCardType.DANGER, value=2)] * 3
            + [TravelCard(type=TravelCardType.DANGER, value=3)] * 3
            + [TravelCard(type=TravelCardType.DANGER, value=4)] * 3
            + [TravelCard(type=TravelCardType.DANGER, value=5)] * 3
            + [TravelCard(type=TravelCardType.TRINKET)] * 2
        )
        random.shuffle(cards)
        for _ in range((len(cards) // 10) + 1):
            cards.pop()
        return cards

    def _draw_camp_card(self) -> FullCard:
        camp_template = TemplateCard(
            copies=1,
            name="Rest and Relaxation",
            desc=f"What happens at camp stays at camp",
            unsigned=True,
            type=TemplateCardType.CHOICE,
            data=Choices(
                min_choices=0,
                max_choices=1,
                is_random=False,
                choice_list=[
                    Choice(benefit=(Effect(type=EffectType.MODIFY_HEALTH, value=10),)),
                    Choice(benefit=(Effect(type=EffectType.MODIFY_COINS, value=10),)),
                    Choice(benefit=(Effect(type=EffectType.LEADERSHIP, value=-20),)),
                    Choice(
                        benefit=(Effect(type=EffectType.MODIFY_RESOURCES, value=10),)
                    ),
                ],
            ),
        )
        return make_card(None, camp_template, 1, EncounterContextType.CAMP)

        # if not self._data.camp_deck:
        #     template_deck = load_deck("Camp")
        #     additional: List[TemplateCard] = []
        #     job = load_job(self.job_name)
        #     self._data.camp_deck = actualize_deck(
        #         template_deck, job.rank + 1, EncounterContextType.CAMP, additional
        #     )

        # return self._data.camp_deck.pop(0)

    def _job_check(self, modifier: int) -> Tuple[str, Optional[str], bool]:
        target_number = 4 - modifier
        bonus = self._data.reputation // 4
        roll = random.randint(1, 8) + bonus
        jobs = load_jobs()
        next_job: Optional[str] = None
        is_promo = False
        if roll < target_number - 4:
            bad_jobs = [j for j in jobs if j.rank == 0]
            next_job = (random.choice(bad_jobs)).name
        elif roll < target_number:
            lower_jobs = [j for j in jobs if self._data.job_name in j.promotions]
            if lower_jobs:
                next_job = (random.choice(lower_jobs)).name
            else:
                bad_jobs = [j for j in jobs if j.rank == 0]
                next_job = (random.choice(bad_jobs)).name
        elif roll < target_number + 4:
            next_job = None
        else:
            cur_job = [j for j in jobs if j.name == self._data.job_name][0]
            promo_jobs = [j for j in jobs if j.name in cur_job.promotions]
            if promo_jobs:
                next_job = (random.choice(promo_jobs)).name
                is_promo = True
            else:
                next_job = None
        return (f"1d8+{bonus} vs {target_number}: {roll}", next_job, is_promo)


class CharacterContext:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "Character":
        self._data = CharacterStorage.load_by_name(self.name)
        return Character(self._data)

    def __exit__(self, *exc: Any) -> None:
        CharacterStorage.update(self._data)


class LeadershipMetaField(IntEntityField):
    def __init__(self):
        super().__init__(
            "leadership challenge",
            EffectType.LEADERSHIP,
            None,
            init_v=lambda e: 0,
            set_v=self._do_disrupt,
            min_value=lambda _: -20,
            max_value=lambda _: 20,
        )

    def _do_disrupt(self, entity: Entity, val: int) -> bool:
        job_msg, new_job, is_promo = entity._job_check(val)
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                0,
                1 if new_job else 0,
                [job_msg],
            )
        )

        if new_job:
            self._split_effects[(EffectType.MODIFY_JOB, None)].append(
                Effect(EffectType.MODIFY_JOB, new_job, comment="leadership challenge")
            )
            if is_promo:
                entity._schedule_promotion(entity.job_name)
            else:
                self._split_effects[(EffectType.TRANSPORT, None)].append(
                    Effect(EffectType.TRANSPORT, 3, comment="leadership challenge")
                )
        else:
            self._split_effects[(EffectType.MODIFY_REPUTATION, None)].append(
                Effect(EffectType.MODIFY_REPUTATION, -2, comment="leadership challenge")
            )

        # we are handling the records ourselves
        return False


class ModifyJobField(EntityField):
    def __init__(self):
        super().__init__("job", EffectType.MODIFY_JOB, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        # don't actually switch multiple times
        if not is_last:
            return
        old_job = self._entity.job_name
        self._entity._data.tableau = []
        self._entity._data.job_deck = []
        self._entity._data.job_name = effect.value
        self._entity.refill_tableau()
        self._split_effects[(EffectType.MODIFY_REPUTATION, None)].append(
            Effect(
                EffectType.MODIFY_REPUTATION,
                3,
                is_absolute=True,
                comment="set from job switch",
            )
        )
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                old_job,
                self._entity.job_name,
                [effect.comment] if effect.comment else [],
            )
        )


class ResourceDrawMetaField(IntEntityField):
    def __init__(self):
        super().__init__(
            "resource draws",
            EffectType.MODIFY_RESOURCES,
            None,
            init_v=lambda e: 0,
            set_v=self._do_both,
        )

    def _do_both(self, entity: Entity, val: int) -> bool:
        if val < 0:
            self._do_discard(entity, val)
        elif val > 0:
            self._do_draw(entity, val)
        # if == 0, do nothing
        return False

    def _do_discard(self, entity: Entity, val: int) -> None:
        cur_rs = [
            nm for rs, cnt in self._entity._data.resources.items() for nm in [rs] * cnt
        ]
        to_rm = random.sample(cur_rs, val * -1) if len(cur_rs) > val * -1 else cur_rs
        rcs = defaultdict(int)
        for rt in to_rm:
            rcs[rt] += 1
        for rt, cnt in rcs.items():
            self._split_effects[(EffectType.MODIFY_RESOURCES, rt)].append(
                Effect(
                    EffectType.MODIFY_RESOURCES,
                    -cnt,
                    subtype=rt,
                    comment=f"random pick {-cnt}",
                )
            )
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                0,
                val,
                [f"{k} x{v}" for k, v in rcs.items()],
            )
        )

    def _do_draw(self, entity: Entity, val: int) -> None:
        board = load_board()
        loc = board.get_token_location(self._entity.name)
        comments = []
        for _ in range(val):
            draw = board.draw_resource_card(loc)
            if draw.value != 0:
                self._split_effects[(EffectType.MODIFY_RESOURCES, draw.type)].append(
                    Effect(
                        EffectType.MODIFY_RESOURCES,
                        draw.value,
                        subtype=draw.type,
                    )
                )
            comments.append(draw.name)
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                0,
                val,
                comments,
            )
        )


class TransportField(IntEntityField):
    def __init__(self):
        super().__init__(
            "transport",
            EffectType.TRANSPORT,
            None,
            init_v=lambda e: 0,
            set_v=self._do_transport,
        )

    def _do_transport(self, entity: Entity, val: int) -> None:
        board = load_board()
        tp_mod = val // 5 + 1
        tp_min = clamp(val - tp_mod, min=1)
        tp_max = val + tp_mod
        old_location = board.get_token_location(self._entity.name)
        new_location = random.choice(
            board.find_hexes_near_token(self._entity.name, tp_min, tp_max)
        )
        board.move_token(
            self._entity.name,
            new_location,
            adjacent=False,
            comments=[f"random {tp_min}-{tp_max} hex transport"],
            records=self._records,
        )


class ModifyLocationField(EntityField):
    def __init__(self):
        super().__init__("location", EffectType.MODIFY_LOCATION, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        # don't actually switch multiple times
        if not is_last:
            return
        board.move_token(
            self._entity.name,
            effect.value,
            adjacent=False,
            comments=[],
            records=self._records,
        )


class ModifyActivityField(IntEntityField):
    def __init__(self):
        super().__init__(
            "available activity",
            EffectType.MODIFY_ACTIVITY,
            None,
            init_v=lambda e: 0
            if TurnFlags.ACTED in self._entity._data.turn_flags
            else 1,
            set_v=self._do_action,
        )

    def _do_action(self, entity: Entity, val: int) -> None:
        if val <= 0:
            self._entity._data.turn_flags.add(TurnFlags.ACTED)
        else:
            self._entity._data.turn_flags.discard(TurnFlags.ACTED)


class AddEmblemField(EntityField):
    def __init__(self):
        super().__init__("emblems", EffectType.ADD_EMBLEM, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        old_idxs = [
            idx
            for idx in range(len(self._entity._data.emblems))
            if self._entity._data.emblems[idx].name == effect.value.name
        ]
        if old_idxs:
            old_emblem = self._entity._data.emblems.pop(old_idxs[0])
            new_emblem = Gadget(
                name=effect.value.name, desc=None, rules=old_emblem.rules + effect.value.rules, triggers=old_emblem.triggers + effect.value.triggers,
            )
        else:
            old_emblem = None
            new_emblem = effect.value
        self._entity._data.emblems.append(new_emblem)
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                old_emblem,
                new_emblem,
                [],
            )
        )


class QueueEncounterField(EntityField):
    def __init__(self):
        super().__init__("emblems", EffectType.QUEUE_ENCOUNTER, None)

    def _update(
        self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool
    ) -> None:
        template = effect.value
        # this isn't right but probably ok for now
        context_type = (
            EncounterContextType.ACTION if enforce_costs else EncounterContextType.JOB
        )
        card = make_card(None, template, 1, context_type)
        self._entity._queue_encounter(card)
        self._records.append(
            Record(
                make_id(),
                self._entity.ENTITY_TYPE,
                self._entity.name,
                self._type,
                self._subtype,
                None,
                template,
                [],
            )
        )


class ModifyFreeXpField(IntEntityField):
    def __init__(self):
        super().__init__(
            "free xp",
            EffectType.MODIFY_XP,
            None,
            init_v=lambda e: 0,
            set_v=self._do_modify,
        )

    def _do_modify(self, entity: Entity, val: int) -> None:
        if val <= 0:
            raise Exception("Don't know how to subtract unassigned xp yet")
        else:
            self._entity._distribute_free_xp(val)


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
    remaining_turns: int
    luck: int
    emblems: List[Gadget]
    tableau: List[TableauCard]
    encounter: Optional[Encounter]
    queued: List[FullCard]
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
