import dataclasses
from pathlib import Path
from typing import List, Optional, Sequence

from .board import load_board
from .character import Character, TurnFlags
from .exceptions import BadStateException, IllegalMoveException
from .game import create_game
from .project import Project, ProjectStage
from .snapshot import (
    Board as snapshot_Board,
    Character as snapshot_Character,
    Project as snapshot_Project,
)
from .storage import ConnectionManager, with_connection
from .types import (
    Action,
    Choices,
    EncounterActions,
    EncounterContextType,
    Outcome,
    TemplateCard,
)


class Engine:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)

    @with_connection()
    def create_game(self, name: str, json_dir: Path, *, player_id: int) -> int:
        game = create_game(name, json_dir)
        # create_game fixes the game_id in the session, so we can just call this:
        board = load_board()
        board.generate_map()
        return game.id

    @with_connection()
    def add_character(
        self,
        location: str,
        job_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> None:
        Character.create(character_name, player_id, job_name, location)
        with Character.load(character_name) as ch:
            ch.refill_tableau()

    @with_connection()
    def get_board(
        self, *, player_id: int, game_id: int, character_name: str
    ) -> snapshot_Board:
        board = load_board()
        return board.get_snapshot(character_name)

    @with_connection()
    def get_character(
        self, *, player_id: int, game_id: int, character_name: str
    ) -> snapshot_Character:
        with Character.load(character_name) as ch:
            return ch.get_snapshot()

    @with_connection()
    def get_projects(
        self, include_all: bool, *, player_id: int, game_id: int, character_name: str
    ) -> List[snapshot_Project]:
        return Project.get_snapshots(character_name, include_all)

    @with_connection()
    def create_project(
        self,
        name: str,
        project_type: str,
        location: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> None:
        Project.create(name, project_type, location)
        with Project.load(name) as proj:
            from .types import ProjectStageType

            proj.add_stage(ProjectStageType.WAITING)

    @with_connection()
    def start_project_stage(
        self,
        project_name: str,
        stage_num: int,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Outcome:
        with ProjectStage.load(project_name, stage_num) as stage:
            with Character.load(character_name) as ch:
                current = Project.get_snapshots(character_name, False)
                cur_count = sum(len(p.stages) for p in current)
                if cur_count >= ch.get_max_project_stages():
                    raise IllegalMoveException(
                        "You are already at your maximum number of open stages."
                    )

                # other requirements could be checked here

                events: List[Event] = []
                cost = [dataclasses.replace(ct, is_cost=True) for ct in stage.cost]
                ch.apply_effects(cost, EncounterContextType.SYSTEM, events)

                stage.start(ch.name)
                return Outcome(events=events)

    @with_connection()
    def do_job(
        self, card_id: int, *, player_id: int, game_id: int, character_name: str
    ) -> Outcome:
        with Character.load(character_name) as ch:
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_tableau_card(card_id)
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=[])

    @with_connection()
    def token_action(
        self,
        token_name: str,
        action_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Outcome:
        with Character.load(character_name) as ch:
            self._basic_action_prep(ch, consume_action=False)

            board = load_board()
            ch_location = board.get_token_location(ch.name)
            token_location = board.get_token_location(token_name)
            if ch_location != token_location:
                raise IllegalMoveException(
                    f"You must be in hex {token_location} to perform that action."
                )
            action = board.get_token_action(token_name, action_name)
            ch.queue_template(
                self._action_to_template(action),
                context_type=EncounterContextType.ACTION,
            )
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=[])

    def _action_to_template(self, action: Action) -> TemplateCard:
        return TemplateCard(
            copies=1,
            name=action.name,
            desc="...",
            choices=action.choices,
        )

    @with_connection()
    def camp(self, player_id: int, game_id: int, character_name: str) -> Outcome:
        with Character.load(character_name) as ch:
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_camp_card()
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=[])

    @with_connection()
    def travel(
        self, step: str, *, player_id: int, game_id: int, character_name: str
    ) -> Outcome:
        with Character.load(character_name) as ch:
            self._travel_prep(ch)
            events: List[Event] = []
            ch.step(step, events)
            board = load_board()
            ch.queue_travel_card(board.get_token_location(character_name))
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=events)

    @with_connection()
    def end_turn(self, *, player_id: int, game_id: int, character_name: str) -> Outcome:
        with Character.load(character_name) as ch:
            self._basic_action_prep(ch, consume_action=True)
            if not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=[])

    @with_connection()
    def resolve_encounter(
        self,
        actions: EncounterActions,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Outcome:
        with Character.load(character_name) as ch:
            events: List[Event] = []

            encounter = ch.pop_encounter()
            effects = ch.calc_effects(encounter, actions)
            ch.apply_effects(effects, encounter.context_type, events)
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch)
            return Outcome(events=events)

    def _basic_action_prep(self, ch: Character, consume_action: bool) -> None:
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if consume_action:
            if not ch.check_set_flag(TurnFlags.ACTED):
                raise BadStateException("You have already acted this turn.")

    def _travel_prep(self, ch: Character) -> None:
        if ch.encounters:
            raise BadStateException("An encounter is currently active.")
        if ch.speed <= 0:
            raise IllegalMoveException(f"You have no remaining speed.")
        if ch.acted_this_turn():
            raise IllegalMoveException(f"You can't move in a turn after having acted.")

    # currently we assume nothing in here adds to the current list of events,
    # to avoid confusing the player when additional stuff shows up in the
    # outcome, but there's probably nothing strictly wrong if it did
    def _finish_turn(self, ch: Character) -> None:
        self._bad_reputation_check(ch)
        if ch.encounters:
            return

        self._discard_resources(ch)
        if ch.encounters:
            return

        ch.turn_reset()

        # filter to encounters near the PC (since they may have been transported, or just moved)
        board = load_board()
        near: Set[str] = {hx for hx in board.find_hexes_near_token(ch.name, 0, 5)}
        ch.age_tableau(near)
        ch.refill_tableau()

    def _bad_reputation_check(self, ch: Character) -> None:
        if ch.reputation > 0:
            return

        if ch.check_set_flag(TurnFlags.BAD_REP_CHECKED):
            return

        job_template = TemplateCard(
            copies=1,
            name="Bad Reputation",
            desc=f"Automatic job check at zero reputation.",
            unsigned=True,
            choices=Choices(
                min_choices=1,
                max_choices=1,
                is_random=False,
                choice_list=[
                    [
                        Choice(
                            benefit=(
                                Effect(
                                    type=EffectType.DISRUPT_JOB, subtype=None, value=-1
                                ),
                            )
                        )
                    ],
                ],
            ),
        )
        ch.queue_template(job_template, context_type=EncounterContextType.SYSTEM)

    def _discard_resources(self, ch: Character) -> None:
        # discard down to correct number of resources
        # (in the future should let player pick which to discard)
        all_rs = [nm for rs, cnt in ch.resources.items() for nm in [rs] * cnt]
        overage = len(all_rs) - ch.get_max_resources()
        if overage <= 0:
            return

        discard_template = TemplateCard(
            copies=1,
            name="Discard Resources",
            desc=f"You must discard to {ch.get_max_resources()} resources.",
            unsigned=True,
            choices=Choices(
                min_choices=overage,
                max_choices=overage,
                is_random=False,
                choice_list=[
                    Choice(
                        cost=(
                            Effect(
                                type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1
                            ),
                        )
                    )
                    for rs in all_rs
                ],
            ),
        )
        ch.queue_template(discard_template, context_type=EncounterContextType.SYSTEM)
