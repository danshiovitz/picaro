import dataclasses
import random
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from itertools import groupby
from typing import Any, Dict, Generic, List, Optional, Sequence, Set, Tuple, TypeVar

from .board import ActiveBoard as Board
from .deck import load_deck
from .exceptions import BadStateException, IllegalMoveException
from .job import load_job, load_jobs
from .skills import load_skills
from .storage import ObjectStorageBase
from .types import Character as CharacterSnapshot, ChoiceType, DrawnCard, Encounter, Effect, EffectType, FullCard, TemplateCard, Token


@dataclass(frozen=True)
class EncounterActions:
    adjusts: Sequence[int]
    transfers: Sequence[Tuple[int, int]]
    flee: bool
    luck: int
    rolls: Sequence[int]
    choice: Optional[int]


T = TypeVar("T")

@dataclass(frozen=True)
class EncounterSingleOutcome(Generic[T]):
    new_val: T
    old_val: T
    comments: List[str]


@dataclass(frozen=True)
class EncounterOutcome:
    coins: Optional[EncounterSingleOutcome[int]]
    xp: Dict[str, EncounterSingleOutcome[int]]
    reputation: Optional[EncounterSingleOutcome[int]]
    health: Optional[EncounterSingleOutcome[int]]
    resources: Optional[EncounterSingleOutcome[int]]
    quest: Optional[EncounterSingleOutcome[int]]
    transport_location: Optional[EncounterSingleOutcome[str]]
    new_job: Optional[EncounterSingleOutcome[str]]


class Party:
    def create_character(self, name: str, player_id: int, job_name: str, board: Board, location: str) -> None:
        ch = Character(
            name=name,
            player_id=player_id,
            job_name=job_name,
            skill_xp={},
            health=0,
            coins=0,
            resources=0,
            reputation=0,
            quest=0,
            remaining_turns=0,
            luck=0,
            tableau=[],
            encounters=[],
            job_deck=[],
            camp_deck=[],
            acted_this_turn=False,
        )
        ch.health = ch.get_max_health()
        board.add_token(Token(name=name, type="Character", location=location))
        return CharacterStorage.create(ch)

    def get_character(self, name: str, board: Board) -> CharacterSnapshot:
        ch = CharacterStorage.load_by_name(name)
        all_skills = load_skills()
        location = board.get_token(ch.name).location
        return CharacterSnapshot(
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
            tableau=tuple(ch.tableau),
            encounters=tuple(ch.encounters),
        )

    def start_season(self, board: Board) -> None:
        for ch in CharacterStorage.load():
            ch.start_season(board)
            CharacterStorage.update(ch)

    def finish_season(self, board: Board) -> None:
        raise Exception("Not implemented yet")

    def do_job(self, name: str, card_id: int, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        ch.check_can_act()
        ch.acted_this_turn = True
        card = ch.remove_tableau_card(card_id)
        ch.queue_encounter(card.card)
        board.move_token(ch.name, card.location_name, adjacent=False)
        CharacterStorage.update(ch)

    def do_travel(self, name: str, route: List[str], board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        ch.check_can_act()
        ch.acted_this_turn = True
        for hx in route:
            board.move_token(ch.name, hx, adjacent=True)
        card = board.draw_hex_card(route[-1])
        ch.queue_encounter(card)
        CharacterStorage.update(ch)

    def do_camp(self, name: str, board: Board) -> None:
        ch = CharacterStorage.load_by_name(name)
        ch.check_can_act()
        ch.acted_this_turn = True
        card = ch.draw_camp_card(board)
        ch.queue_encounter(card)
        CharacterStorage.update(ch)

    def resolve_encounter(self, name: str, actions: EncounterActions, board: Board) -> EncounterOutcome:
        ch = CharacterStorage.load_by_name(name)
        outcome = ch.resolve_encounter(actions, board)
        CharacterStorage.update(ch)
        return outcome


DRAW_HEX_CARD = TemplateCard(1, name="Draw from Hex Deck", desc="", skills=[], rewards=[], penalties=[], choice_type=ChoiceType.NONE, choices=[])


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
    tableau: List[DrawnCard]
    encounters: List[Encounter]
    job_deck: List[FullCard]
    camp_deck: List[FullCard]
    acted_this_turn: bool

    def get_init_turns(self) -> int:
        return 20

    def get_max_luck(self) -> int:
        return 5

    def get_max_tableau_size(self) -> int:
        return 3

    def get_card_age(self) -> int:
        return 3

    def get_max_health(self) -> int:
        return 20

    def get_skill_rank(self, skill_name: str) -> int:
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        xp = self.skill_xp.get(skill_name, 0)
        if xp < 20:
            return 0
        elif 20 <= xp < 45:
            return 1
        elif 45 <= xp < 70:
            return 2
        elif 70 <= xp < 95:
            return 3
        elif 95 <= xp < 125:
            return 4
        else:
            return 5

    def start_season(self, board: Board) -> None:
        # leave the encounters queue alone, since there
        # might be stuff from the rumors phase
        self.tableau = []
        self.remaining_turns = self.get_init_turns()
        self.luck = self.get_max_luck()
        self.refill_tableau(board)

    def refill_tableau(self, board: Board) -> None:
        job = load_job(self.job_name)
        if not self.job_deck:
            self.job_deck = job.make_deck(additional=[dataclasses.replace(DRAW_HEX_CARD, copies=2)])

        while len(self.tableau) < self.get_max_tableau_size():
            card = self.job_deck.pop(0)
            dst = random.choice(job.encounter_distances)
            location = random.choice(board.find_hexes_near_token(self.name, dst, dst))

            if card.name == DRAW_HEX_CARD.name:
                card = board.draw_hex_card(location)

            self.tableau.append(DrawnCard(card=card, location_name=location, age=self.get_card_age()))

    def remove_tableau_card(self, card_id) -> DrawnCard:
        idx = [i for i in range(len(self.tableau)) if self.tableau[i].card.id == card_id]
        if not idx:
            raise BadStateException(f"No such encounter card found ({card_id})")
        return self.tableau.pop(idx[0])

    def queue_encounter(self, card: FullCard) -> None:
        rolls = []
        for chk in card.checks:
            bonus = self.get_skill_rank(chk.skill)
            rolls.append(random.randint(1, 8) + bonus)
        if card.choice_type == ChoiceType.RANDOM:
            rolls.append(random.randint(1, len(card.choices)))
        self.encounters.append(Encounter(card=card, rolls=rolls))

    def check_can_act(self) -> None:
        if self.encounters:
            raise BadStateException("An encounter is currently active.")
        if self.acted_this_turn:
            raise BadStateException("You have already acted this turn.")

    def resolve_encounter(self, actions: EncounterActions, board: Board) -> EncounterOutcome:
        if not self.encounters:
            raise BadStateException("There is no active encounter.")

        encounter = self.encounters.pop(0)
        effects = self._calc_effects(encounter, actions)
        outcome = self._apply_effects(effects, board)

        if not self.encounters:
            self._finish_turn(board)

        return outcome

    # note this does update luck as well as validating stuff
    def _validate_actions(self, encounter: Encounter, actions: EncounterActions) -> None:
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
            if actions.choice is None and encounter.card.choice_type == ChoiceType.REQUIRED:
                raise BadStateException("Choice must be supplied")
            if encounter.card.choice_type == ChoiceType.RANDOM:
                if actions.choice != encounter.rolls[-1] - 1:
                    raise BadStateException("Choice should match roll for random")
            if actions.choice is not None and (actions.choice < 0 or actions.choice >= len(encounter.card.choices)):
                raise BadStateException(f"Choice out of range ({actions.choice}, max {len(encounter.card.choices)})")
        else:
            if actions.choice is not None:
                raise BadStateException("Choice not allowed here")

    def _calc_effects(self, encounter: Encounter, actions: EncounterActions) -> List[Effect]:
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
            ret.extend(Effect(type=k, rank=v, param=vals.get(k, None)) for k, v in ocs.items())

        if actions.choice is not None:
            ret.extend(encounter.card.choices[actions.choice])

        return ret

    def _apply_effects(self, effects: List[Effect], board: Board) -> EncounterOutcome:
        # want something like: first process gain coins, if any, then process lose coins, if any,
        # then gain resources, then lose resources, ... , then job change, then pick the actual
        # transport location if any
        # we do it this way because we want, eg, to be able to overwrite reputation changes with
        # reputation set via job change (note that any 'set' overwrites previous comments, as well)

        def simple_eff(eff_type, mods, val_fn):
            for eff in (eff for eff in effects if eff.type == eff_type):
                v = val_fn(eff.rank)
                tup = (v, None, f"{v:+}")
                if eff.param:
                    mods[eff.param].append(tup)
                else:
                    mods.append(tup)

        sum_til = lambda v: (v * v + v) // 2

        coins_mods = []
        rep_mods = []
        health_mods = []
        quest_mods = []
        xp_mods = defaultdict(list)
        resrc_mods = []
        transport_mods = []
        job_mods = None

        simple_eff(EffectType.GAIN_COINS, coins_mods, lambda rank: sum_til(rank))
        simple_eff(EffectType.LOSE_COINS, coins_mods, lambda rank: -rank)
        simple_eff(EffectType.GAIN_REPUTATION, rep_mods, lambda rank: sum_til(rank))
        simple_eff(EffectType.LOSE_REPUTATION, rep_mods, lambda rank: -rank)
        simple_eff(EffectType.GAIN_HEALING, health_mods, lambda rank: rank * 3)
        simple_eff(EffectType.DAMAGE, health_mods, lambda rank: -rank)
        simple_eff(EffectType.GAIN_QUEST, quest_mods, lambda rank: rank)
        simple_eff(EffectType.GAIN_XP, xp_mods, lambda rank: rank * 3)
        simple_eff(EffectType.CHECK_FAILURE, xp_mods, lambda rank: rank)
        simple_eff(EffectType.GAIN_RESOURCES, resrc_mods, lambda rank: rank - 1)
        simple_eff(EffectType.LOSE_RESOURCES, resrc_mods, lambda rank: -rank)
        simple_eff(EffectType.TRANSPORT, transport_mods, lambda rank: rank * 5)
        for eff in (eff for eff in effects if eff.type == EffectType.DISRUPT_JOB):
            msg, new_job = self._job_check(eff.rank)
            if new_job:
                job_mods = [(new_job, msg)]
                # blow away earlier rep mods:
                rep_mods = [(None, 3, "set to 3 for job switch")]
                transport_mods = [(3, None, "+3")]
            else:
                rep_mods.append((-2, None, "-2"))

        def make_single(mods, field, max_val=None, min_val=0):
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
            return EncounterSingleOutcome[int](old_val=old_val, new_val=new_val, comments=msgs)

        def make_xp(mods):
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
                ret[key] = EncounterSingleOutcome[int](old_val=old_val, new_val=new_val, comments=msgs)
            return ret

        def make_transport(mods):
            if not mods:
                return None
            tp = 0
            msgs = []
            for mod, flat, msg in mods:
                if mod is not None:
                    tp += mod
                if flat is not None:
                    tp = flat
                if msg is not None:
                    msgs.append(msg)
            if tp <= 0:
                return None
            location = random.choice(board.find_hexes_near_token(self.name, tp - 2, tp + 2))
            old_loc = board.get_token(self.name).location
            board.move_token(self.name, location)
            return EncounterSingleOutcome[str](old_val=old_loc, new_val=location, comments=msgs)

        def make_job(mods):
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
            return EncounterSingleOutcome[str](old_val=old_job, new_val=new_job, comments=msgs)

        return EncounterOutcome(
            coins=make_single(coins_mods, "coins"),
            reputation=make_single(rep_mods, "reputation"),
            xp=make_xp(xp_mods),
            health=make_single(health_mods, "health", max_val=self.get_max_health()),
            resources=make_single(resrc_mods, "resources"),
            quest=make_single(quest_mods, "quest"),
            transport_location=make_transport(transport_mods),
            new_job=make_job(job_mods),
        )

    def _finish_turn(self, board: Board) -> None:
        self.remaining_turns -= 1
        self.acted_this_turn = False

        # filter to encounters near the PC (since they may have been transported, or just moved)
        near : Set[str] = {hx for hx in board.find_hexes_near_token(self.name, 0, 5)}

        def _is_valid(card: DrawnCard) -> bool:
            return card.age > 1 and card.location_name in near

        self.tableau = [dataclasses.replace(c, age=c.age - 1) for c in self.tableau if _is_valid(c)]
        self.refill_tableau(board)

    def draw_camp_card(self, board: Board) -> FullCard:
        if not self.camp_deck:
            template_deck = load_deck("Camp")
            additional = []
            job = load_job(self.job_name)
            self.camp_deck = template_deck.actualize(job.rank + 1, additional)

        return self.camp_deck.pop(0)

    def _job_check(self, modifier: int) -> Tuple[str, Optional[str]]:
        target_number = 5 + modifier
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
            raise Exception(f"No such character: {name}")
        return chars[0]

    @classmethod
    def create(cls, character: Character) -> Character:
        cls._insert_helper([character])
        return character

    @classmethod
    def update(cls, character: Character) -> Character:
        cls._update_helper(character)
        return character
