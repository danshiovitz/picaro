import random
from collections import defaultdict
from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Set, Tuple

from .board import Board
from .deck import Deck, EncounterDeck
from .job import Job
from .skills import SKILLS
from .types import DrawnCard, EncounterReward, EncounterPenalty, FullCard
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
    coins: int
    xp: int
    reputation: int
    health: int
    resources: int
    quest: int
    transport_location: Optional[str]


class Character:
    def __init__(self, name: str, player_id: int, job: Job) -> None:
        self.name = name
        self.player_id = player_id
        self.job = job
        self.skills = {s: 0 for s in SKILLS}
        self.skill_xp = {s: 0 for s in SKILLS}
        self.health = 20
        self.coins = 0
        self.resources = 0
        self.reputation = 0
        self.quest = 0
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
        return DrawnCard(card=card, location_name=location.name, age=3)

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
                board.move_token(self.name, card.location_name, adjacent=False)
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

        self.tableau.luck = luck

        coins_mod = 0
        xp_mod = 0
        reputation_mod = 0
        health_mod = 0
        resources_mod = 0
        quest_mod = 0
        do_demotion = False
        transport_distance = 0

        ocs = defaultdict(int)

        for idx, check in enumerate(self.tableau.encounter.card.checks):
            if rolls[idx] >= check.target_number:
                ocs[check.reward] += 1
            else:
                ocs[check.penalty] += 1
                xp_mod += 1

        for oc, cnt in ocs.items():
            if oc == EncounterReward.COINS:
                coins_mod += (cnt * 2 - 1)
            elif oc == EncounterReward.XP:
                xp_mod += cnt * 2
            elif oc == EncounterReward.REPUTATION:
                reputation_mod += cnt
            elif oc == EncounterReward.HEALING:
                health_mod += cnt * 3
            elif oc == EncounterReward.RESOURCES:
                if cnt == 3:
                    resources_mod += 2
                elif cnt == 2:
                    resources_mod += 1
            elif oc == EncounterReward.QUEST:
                quest_mod += cnt
            elif oc == EncounterReward.NOTHING:
                pass
            elif oc == EncounterPenalty.COINS:
                coins_mod -= cnt
            elif oc == EncounterPenalty.REPUTATION:
                reputation_mod -= 1
            elif oc == EncounterPenalty.DAMAGE:
                health_mod -= cnt
            elif oc == EncounterPenalty.RESOURCES:
                resources_mod -= 1
            elif oc == EncounterPenalty.JOB:
                do_demotion = True
            elif oc == EncounterPenalty.TRANSPORT:
                transport_distance += cnt * 5
            elif oc == EncounterPenalty.NOTHING:
                pass
            else:
                raise Exception(f"Unknown reward/penalty: {oc.name}")

        transport_location: Optional[str] = None

        if coins_mod != 0:
            self.coins += coins_mod
        if xp_mod != 0:
            self._adjust_xp(self.tableau.encounter.card.checks[0].skill, xp_mod)
        if reputation_mod != 0:
            self.reputation += reputation_mod
        if health_mod != 0:
            self.health += health_mod
        if resources_mod != 0:
            self.resources += resources_mod
        if quest_mod != 0:
            self.quest += quest_mod
        if transport_distance > 0:
            location = random.choice(board.find_hexes_near_location(self.name, transport_distance - 5, transport_distance))
            transport_location = location.name
            board.move_token(self.name, transport_location)

        outcome = EncounterOutcome(
            coins=coins_mod,
            xp=xp_mod,
            reputation=reputation_mod,
            health=health_mod,
            resources=resources_mod,
            quest=quest_mod,
            transport_location=transport_location,
        )

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

        # filter to encounters near the PC (since they may have been transported, or just moved)
        near : Set[str] = {hx.name for hx in board.find_hexes_near_location(self.name, 0, 5)}

        def _is_valid(card: DrawnCard) -> bool:
            return card.age > 1 and card.location_name in near

        self.tableau.cards = [c._replace(age=c.age - 1) for c in self.tableau.cards if _is_valid(c)]
        while len(self.tableau.cards) < self.tableau_size:
            self.tableau.cards.append(self.draw_job_card(board))

    def _adjust_xp(self, skill: str, xp_mod: int) -> None:
        self.skill_xp[skill] += xp_mod
        # 20 xp for rank 1, 30 xp for rank 5, 25 xp for all others
        if self.skill_xp[skill] < 20:
            self.skills[skill] = 0
        elif 20 <= self.skill_xp[skill] < 45:
            self.skills[skill] = 1
        elif 45 <= self.skill_xp[skill] < 70:
            self.skills[skill] = 2
        elif 70 <= self.skill_xp[skill] < 95:
            self.skills[skill] = 3
        elif 95 <= self.skill_xp[skill] < 125:
            self.skills[skill] = 4
        else:
            self.skills[skill] = 5
