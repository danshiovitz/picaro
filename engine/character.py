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
    ChoiceType,
    TableauCard,
    Effect,
    EffectType,
    Emblem,
    Encounter,
    EncounterActions,
    EncounterContextType,
    EncounterOutcome,
    EncounterSingleOutcome,
    Feat,
    FullCard,
    HookType,
    JobType,
    TemplateCard,
    Token,
)


class Party:
    def create_character(
        self, name: str, player_id: int, job_name: str, board: Board, location: str
    ) -> None:
        ch = Character.create(name, player_id, job_name)
        board.add_token(Token(name=name, type="Character", location=location))
        return CharacterStorage.create(ch)

    def get_character(self, name: str, board: Board) -> snapshot_Character:
        ch = CharacterStorage.load_by_name(name)
        all_skills = load_skills()
        location = board.get_token(ch.name).location
        return snapshot_Character(
            name=ch.name,
            player_id=ch.player_id,
            skills={sk: ch.get_skill_rank(sk) for sk in all_skills},
            skill_xp={sk: ch.skill_xp.get(sk, 0) for sk in all_skills},
            job=ch.job_name,
            health=ch.health,
            coins=ch.coins,
            resources=ch.resources,
            reputation=ch.reputation,
            quest=ch.quest,
            location=location,
            remaining_turns=ch.remaining_turns,
            luck=ch.luck,
            speed=ch.speed,
            tableau=tuple(
                self._tableau_snapshot(c, board.best_route(location, c.location))
                for c in ch.tableau
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
            choice_type=card.card.choice_type,
            choices=card.card.choices[0:1],
            age=card.age,
            location=card.location,
            route=tuple(route),
        )

    def _encounter_snapshot(self, encounter: Encounter) -> Sequence[snapshot_Encounter]:
        return snapshot_Encounter(
            name=encounter.card.name,
            desc=encounter.card.desc,
            checks=encounter.card.checks,
            choice_type=encounter.card.choice_type,
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
        location = board.get_token(ch.name).location
        if card.location != location:
            raise IllegalMoveException(
                f"You must be in hex {card.location} for that encounter."
            )
        ch.queue_encounter(card.card, context_type=EncounterContextType.JOB)
        board.move_token(ch.name, card.location, adjacent=False)
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
            card = ch.draw_travel_card(board.get_token(ch.name).location, board)
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


TRINKET_CARD = TemplateCard(
    copies=1,
    name="A Find Along The Way",
    desc="",
    skills=[],
    rewards=[],
    penalties=[],
    choice_type=ChoiceType.RANDOM,
    choices=[
        [Effect(type=EffectType.GAIN_HEALING, rank=1)],
        [Effect(type=EffectType.GAIN_COINS, rank=1)],
        [Effect(type=EffectType.GAIN_COINS, rank=3)],
        [Effect(type=EffectType.GAIN_RESOURCES, rank=2)],
        [Effect(type=EffectType.GAIN_QUEST, rank=1)],
    ],
)


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
    resources: int
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
            resources=0,
            reputation=5,
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
            rolls.append(random.randint(1, 8) + bonus)
        if card.choice_type == ChoiceType.RANDOM:
            rolls.append(random.randint(1, len(card.choices)))
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

    def calc_effects(
        self, encounter: Encounter, actions: EncounterActions
    ) -> List[Effect]:
        self._validate_actions(encounter, actions)
        if actions.flee:
            return []

        ret = []

        if encounter.card.checks:
            ocs = defaultdict(int)

            for idx, check in enumerate(encounter.card.checks):
                if encounter.rolls[idx] >= check.target_number:
                    ocs[check.reward] += 1
                else:
                    ocs[check.penalty] += 1
                    ocs[EffectType.CHECK_FAILURE] += 1

            vals = {
                EffectType.GAIN_XP: encounter.card.checks[0].skill,
                EffectType.CHECK_FAILURE: encounter.card.checks[0].skill,
            }
            ret.extend(
                Effect(type=k, rank=v, param=vals.get(k, None)) for k, v in ocs.items()
            )

        if actions.choice is not None:
            ret.extend(encounter.card.choices[actions.choice])

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

        if encounter.card.choice_type != ChoiceType.NONE:
            if (
                actions.choice is None
                and encounter.card.choice_type == ChoiceType.REQUIRED
            ):
                if encounter.card.choices:
                    raise BadStateException("Choice must be supplied")
            if encounter.card.choice_type == ChoiceType.RANDOM:
                if actions.choice != encounter.rolls[-1] - 1:
                    raise BadStateException("Choice should match roll for random")
            if actions.choice is not None and (
                actions.choice < 0 or actions.choice >= len(encounter.card.choices)
            ):
                raise BadStateException(
                    f"Choice out of range ({actions.choice}, max {len(encounter.card.choices)})"
                )
        else:
            if actions.choice is not None:
                raise BadStateException("Choice not allowed here")

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

        coins_mods = []
        rep_mods = []
        health_mods = []
        quest_mods = []
        turn_mods = []
        xp_mods = defaultdict(list)
        resource_mods = []
        speed_mods = []
        transport_mods = []
        job_mods = []

        sum_til = lambda v: (v * v + v) // 2

        self._accumulate_mods(
            effects, EffectType.GAIN_COINS, coins_mods, lambda rank: sum_til(rank)
        )
        self._accumulate_mods(
            effects, EffectType.LOSE_COINS, coins_mods, lambda rank: -rank
        )
        self._accumulate_mods(
            effects, EffectType.GAIN_REPUTATION, rep_mods, lambda rank: sum_til(rank)
        )
        self._accumulate_mods(
            effects, EffectType.LOSE_REPUTATION, rep_mods, lambda rank: -rank
        )
        self._accumulate_mods(
            effects, EffectType.GAIN_HEALING, health_mods, lambda rank: rank * 3
        )
        self._accumulate_mods(
            effects, EffectType.DAMAGE, health_mods, lambda rank: -sum_til(rank)
        )
        self._accumulate_mods(
            effects, EffectType.GAIN_QUEST, quest_mods, lambda rank: rank
        )
        self._accumulate_mods_dict(
            effects, EffectType.GAIN_XP, xp_mods, lambda rank: rank * 5
        )
        self._accumulate_mods_dict(
            effects, EffectType.CHECK_FAILURE, xp_mods, lambda rank: rank
        )
        self._accumulate_mods(
            effects, EffectType.GAIN_RESOURCES, resource_mods, lambda rank: rank - 1
        )
        self._accumulate_mods(
            effects, EffectType.LOSE_RESOURCES, resource_mods, lambda rank: -rank
        )
        self._accumulate_mods(
            effects, EffectType.GAIN_TURNS, turn_mods, lambda rank: rank
        )
        self._accumulate_mods(
            effects, EffectType.LOSE_TURNS, turn_mods, lambda rank: -rank
        )
        self._accumulate_mods(
            effects, EffectType.LOSE_SPEED, speed_mods, lambda rank: -rank
        )
        self._accumulate_mods(
            effects, EffectType.TRANSPORT, transport_mods, lambda rank: rank * 5
        )
        self._accumulate_mods_job_check(effects, job_mods, transport_mods, rep_mods)

        return EncounterOutcome(
            coins=self._make_single_outcome(coins_mods, "coins"),
            reputation=self._make_single_outcome(rep_mods, "reputation"),
            xp=self._make_xp_outcome(xp_mods),
            health=self._make_single_outcome(
                health_mods, "health", max_val=self.get_max_health()
            ),
            resources=self._make_single_outcome(resource_mods, "resources"),
            quest=self._make_single_outcome(quest_mods, "quest"),
            turns=self._make_single_outcome(turn_mods, "remaining_turns"),
            speed=self._make_single_outcome(speed_mods, "speed"),
            transport_location=self._make_transport_outcome(
                transport_mods, context_type, board
            ),
            new_job=self._make_job_outcome(job_mods, board),
        )

    # for simple effects, just append their modifiers to a list
    def _accumulate_mods(
        self,
        effects: List[Effect],
        effect_type: EffectType,
        mods: List[ModTuple],
        val_fn: Callable[[int], int],
    ) -> None:
        for effect in effects:
            if effect.type != effect_type:
                continue
            val = val_fn(effect.rank)
            tup = (val, None, f"{val:+}")
            if effect.param:
                raise Exception(
                    f"Don't know how to handle param {param} here for {effect_type}"
                )
            else:
                mods.append(tup)

    def _accumulate_mods_dict(
        self,
        effects: List[Effect],
        effect_type: EffectType,
        mods: Dict[str, List[ModTuple]],
        val_fn: Callable[[int], int],
    ) -> None:
        for effect in effects:
            if effect.type != effect_type:
                continue
            val = val_fn(effect.rank)
            tup = (val, None, f"{val:+}")
            if effect.param:
                mods[effect.param].append(tup)
            else:
                raise Exception(f"Expected param here for {effect_type}")

    def _accumulate_mods_job_check(
        self,
        effects: List[Effect],
        job_mods: List[Tuple[str, str]],
        transport_mods: List[ModTuple],
        rep_mods: List[ModTuple],
    ) -> None:
        for effect in effects:
            if effect.type != EffectType.DISRUPT_JOB:
                continue
            if effect.param:
                raise Exception(
                    f"Don't know how to handle param {param} here for DISRUPT_JOB"
                )

            msg, new_job = self._job_check(effect.rank)
            if new_job:
                job_mods.clear()
                job_mods.append((new_job, msg))
                # also move some (more)
                transport_mods.append((3, None, "+3"))
                # blow away earlier rep mods:
                rep_mods.clear()
                rep_mods.append((None, 3, "set to 3 for job switch"))
            else:
                rep_mods.append((-2, None, "-2 from job challenge: " + msg))

    def _make_single_outcome(
        self, mods: List[ModTuple], field: str, max_val=None, min_val=0
    ) -> Optional[EncounterSingleOutcome[int]]:
        if not mods:
            return None
        old_val = getattr(self, field)
        new_val = old_val
        msgs = []
        for mod, flat, msg in mods:
            if mod is not None:
                new_val += mod
            if flat is not None:
                new_val = flat
            if msg is not None:
                msgs.append(msg)
        if max_val is not None and new_val > max_val:
            new_val = max_val
        if new_val < min_val:
            new_val = min_val
        setattr(self, field, new_val)
        return EncounterSingleOutcome[int](
            old_val=old_val, new_val=new_val, comments=msgs
        )

    def _make_xp_outcome(
        self, mods: List[ModTuple]
    ) -> Dict[str, EncounterSingleOutcome[int]]:
        if not mods:
            return {}
        ret = {}
        prop = self.skill_xp
        for key in mods:
            old_val = prop.get(key, 0)
            old_rank = self.get_skill_rank(key)
            new_val = old_val
            msgs = []
            for mod, flat, msg in mods[key]:
                if mod is not None:
                    new_val += mod
                if flat is not None:
                    new_val = flat
                if msg is not None:
                    msgs.append(msg)
            prop[key] = new_val
            new_rank = self.get_skill_rank(key)
            if new_rank != old_rank:
                msgs.append(f"new rank is {new_rank}")
            ret[key] = EncounterSingleOutcome[int](
                old_val=old_val, new_val=new_val, comments=msgs
            )
        return ret

    def _make_transport_outcome(
        self,
        transport_mods: List[ModTuple],
        context_type: EncounterContextType,
        board: Board,
    ) -> Optional[EncounterSingleOutcome[str]]:
        new_location: Optional[str] = None
        if transport_mods:
            tp = 0
            msgs = []
            for mod, flat, msg in transport_mods:
                if mod is not None:
                    tp += mod
                if flat is not None:
                    tp = flat
                if msg is not None:
                    msgs.append(msg)
            if tp <= 0:
                return None
            new_location = random.choice(
                board.find_hexes_near_token(self.name, tp - 2, tp + 2)
            )
        if not new_location:
            return None
        old_loc = board.get_token(self.name).location
        board.move_token(self.name, new_location)
        return EncounterSingleOutcome[str](
            old_val=old_loc, new_val=new_location, comments=msgs
        )

    def _make_job_outcome(
        self, mods: List[Tuple[str, str]], board: Board
    ) -> Optional[EncounterSingleOutcome[str]]:
        if not mods:
            return None
        new_job = None
        msgs = []
        for jn, msg in mods:
            if jn is not None:
                new_job = jn
            if msg is not None:
                msgs.append(msg)
        if not new_job:
            return None
        old_job = self.job_name
        self.job_name = new_job
        self.tableau = []
        self.job_deck = []
        self.refill_tableau(board)
        return EncounterSingleOutcome[str](
            old_val=old_job, new_val=new_job, comments=msgs
        )

    def finish_turn(self, board: Board) -> None:
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
            travel_deck = load_deck("Travel")
            return travel_deck.make_card(TRINKET_CARD, 1, EncounterContextType.TRAVEL)
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

    def _job_check(self, modifier: int) -> Tuple[str, Optional[str]]:
        target_number = 4 + modifier
        bonus = self.reputation // 4
        roll = random.randint(1, 8) + bonus
        jobs = load_jobs()
        next_job: Optional[str] = None
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
            else:
                next_job = None
        return (f"1d8+{bonus} vs {target_number}: {roll}", next_job)


class CharacterStorage(ObjectStorageBase[Character]):
    TABLE_NAME = "character"
    TYPE = Character
    PRIMARY_KEY = "name"

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
