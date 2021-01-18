import random
from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Tuple

from .board import Board
from .deck import Deck, EncounterDeck
from .job import Job
from .skills import SKILLS
from .types import DrawnCard, FullCard
from .zodiacs import ZODIACS


class Encounter(NamedTuple):
    card: FullCard
    rolls: List[int]


@dataclass
class Tableau:
    cards: List[DrawnCard]
    encounter: Optional[Encounter]
    remaining_turns: int
    luck: int
    deck: EncounterDeck


class EncounterActions(NamedTuple):
    adjusts: List[int]
    transfers: List[Tuple[int, int]]
    flee: bool
    luck: int
    rolls: List[int]


class EncounterOutcome(NamedTuple):
    damage: int
    coins: int
    reputation: int
    xp: int


class Character:
    def __init__(self, name: str, player_id: int, job: Job) -> None:
        self.name = name
        self.player_id = player_id
        self.job = job
        self.skills = {s: 0 for s in SKILLS}
        self.skill_xp = {s: 0 for s in SKILLS}
        self.health = 20
        self.coins = 0
        self.reputation = 0
        self.tableau: Optional[Tableau] = None
        self.tableau_size = 3

    def start_season(self, board: Board) -> None:
        self.tableau = Tableau(
            cards=[],
            encounter=None,
            remaining_turns=20,
            luck=5,
            deck=self.job.make_deck(),
        )
        for _ in range(self.tableau_size):
            self.tableau.cards.append(self.draw_job_card(board))

    def draw_job_card(self, board: Board) -> DrawnCard:
        if not self.tableau:
            raise Exception("Can't draw when tableau is empty")
        card = self.tableau.deck.draw()
        dst = random.choice(self.job.encounter_distances)
        location = random.choice(board.find_hexes_near_location(self.name, dst, dst))
        return DrawnCard(card=card, location=location, age=3)

    def do_start_encounter(self, card_id: int, board: Board) -> None:
        if not self.tableau:
            raise Exception("Can't start encounter when tableau is empty")
        if self.tableau.encounter:
            raise Exception("An encounter is already active")
        for card in self.tableau.cards:
            if card.card.id == card_id:
                rolls = []
                for chk in card.card.checks:
                    bonus = self.skills[chk.skill]
                    rolls.append(random.randint(1, 8) + bonus)
                self.tableau.encounter = Encounter(card=card.card, rolls=rolls)
                board.move_token(self.name, card.location.name, adjacent=False)
                return
        raise Exception(f"No such encounter card found ({card_id})")

    def do_resolve_encounter(self, actions: EncounterActions, board: Board) -> EncounterOutcome:
        if not self.tableau:
            raise Exception("Can't start encounter when tableau is empty")
        if not self.tableau.encounter:
            raise Exception("There is no active encounter")

        # validate by rerunning actions
        luck = self.tableau.luck
        rolls = self.tableau.encounter.rolls

        for adj in actions.adjusts or []:
            if luck <= 0:
                raise Exception("Luck not high enough for adjust")
            luck -= 1
            rolls[adj] += 1

        for from_c, to_c in actions.transfers or []:
            if rolls[from_c] < 2:
                raise Exception("From not enough for transfer")
            rolls[from_c] -= 2
            rolls[to_c] += 1

        if actions.flee:
            if luck <= 0:
                raise Exception("Luck not high enough for flee")
            luck -= 1

        if (luck, rolls) != (actions.luck, actions.rolls):
            raise Exception("Computed luck/rolls doesn't match?")

        damage_count = 0
        coin_count = 0
        rep_count = 0
        xp_count = 0

        for idx, check in enumerate(self.tableau.encounter.card.checks):
            if rolls[idx] >= check.target_number:
                coin_count += 1
            else:
                damage_count += 1
                xp_count += 1

        outcome = EncounterOutcome(
            damage=damage_count if damage_count > 0 else 0,
            coins=(coin_count * 2 - 1) if coin_count > 0 else 0,
            reputation=(rep_count * 2 - 1) if rep_count > 0 else 0,
            xp=(xp_count * 2 - 1) if xp_count > 0 else 0,
        )
        self.health -= outcome.damage
        self.coins += outcome.coins
        self.reputation += outcome.reputation
        self.skill_xp[self.tableau.encounter.card.checks[0].skill] += outcome.xp

        # pop this off the card list, if it's from there
        self.tableau.cards = [c for c in self.tableau.cards if c.card.id != self.tableau.encounter.card.id]
        self.tableau.encounter = None
        self._finish_turn(board)
        return outcome

    def do_travel(self, route: List[str], board: Board) -> None:
        for hx in route:
            board.move_token(self.name, hx, adjacent=True)
        self._finish_turn()

    def do_camp(self, board: Board) -> None:
        if not self.tableau:
            raise Exception("Can't camp while tableau not present")
        self.health = min(20, self.health + 3)
        self._finish_turn(board)

    def _finish_turn(self, board: Board) -> None:
        if not self.tableau:
            raise Exception("Can't finish turn without tableau?")
        self.tableau.remaining_turns -= 1
        self.tableau.cards = [c._replace(age=c.age - 1) for c in self.tableau.cards if c.age > 1]
        while len(self.tableau.cards) < self.tableau_size:
            self.tableau.cards.append(self.draw_job_card(board))
