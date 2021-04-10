import dataclasses
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Sequence

from picaro.common.utils import with_s

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
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterActions,
    EncounterContextType,
    EncounterEffect,
    EntityType,
    Event,
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
        with Project.load_for_character(character_name) as projects:
            snapshots = (p.get_snapshot(character_name, include_all) for p in projects)
            return [s for s in snapshots if include_all or s.stages]

    @with_connection()
    def xyzzy(
        self,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> None:
        with Character.load(character_name) as ch:
            loc = ch.get_snapshot().location
            ch.apply_effects(
                [
                    Effect(type=EffectType.MODIFY_COINS, value=50),
                    Effect(type=EffectType.MODIFY_RESOURCES, value=50),
                ],
                [],
            )

        project_name = "Quest for Sandwiches"
        Project.create(project_name, "Monument", loc)
        with Project.load(project_name) as proj:
            from .types import ProjectStageType

            proj.add_stage(ProjectStageType.RESOURCE)

        with ProjectStage.load(project_name + " Stage 1") as stage:
            stage.start(character_name, [])

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

    @with_connection()
    def start_project_stage(
        self,
        project_stage_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Outcome:
        with ProjectStage.load(project_stage_name) as stage:
            with Character.load(character_name) as ch:
                with ProjectStage.load_for_character(character_name) as current:
                    if len(current) >= ch.get_max_project_stages():
                        raise IllegalMoveException(
                            "You are already at your maximum number of active stages."
                        )

                # other requirements could be checked here

                events: List[Event] = []
                cost = [dataclasses.replace(ct, is_cost=True) for ct in stage.cost]
                ch.apply_effects(cost, events)

                stage.start(ch.name, events)
                return Outcome(events=events)

    @with_connection()
    def return_project_stage(
        self,
        project_stage_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Outcome:
        with ProjectStage.load(project_stage_name) as stage:
            with Character.load(character_name) as ch:
                events: List[Event] = []
                stage.do_return(ch.name, events)
                return Outcome(events=events)

    @with_connection()
    def do_job(
        self, card_id: int, *, player_id: int, game_id: int, character_name: str
    ) -> Outcome:
        with Character.load(character_name) as ch:
            events: List[Event] = []
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_tableau_card(card_id)
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch, events)
            return Outcome(events=events)

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
            events: List[Event] = []
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
                self._finish_turn(ch, events)
            return Outcome(events=events)

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
            events: List[Event] = []
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_camp_card()
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch, events)
            return Outcome(events=events)

    @with_connection()
    def travel(
        self, step: str, *, player_id: int, game_id: int, character_name: str
    ) -> Outcome:
        with Character.load(character_name) as ch:
            self._travel_prep(ch)
            events: List[Event] = []
            ch.step(step, events)
            board = load_board()
            new_loc = board.get_token_location(ch.name)
            with ProjectStage.load_for_character(ch.name) as current:
                for cur in current:
                    cur.apply_effects(
                        [
                            Effect(
                                EffectType.EXPLORE,
                                new_loc,
                            )
                        ],
                        events,
                    )
            ch.queue_travel_card(new_loc)
            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch, events)
            return Outcome(events=events)

    @with_connection()
    def end_turn(self, *, player_id: int, game_id: int, character_name: str) -> Outcome:
        with Character.load(character_name) as ch:
            events: List[Event] = []
            self._basic_action_prep(ch, consume_action=True)
            if not ch.encounters:
                self._finish_turn(ch, events)
            return Outcome(events=events)

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
            effects = self._compute_encounter_effects(ch, encounter, actions)
            effects = [
                dataclasses.replace(
                    e, entity_type=EntityType.CHARACTER, entity_name=ch.name
                )
                if e.entity_type is None
                else e
                for e in effects
            ]

            effects_split = defaultdict(list)
            for effect in effects:
                effects_split[(effect.entity_type, effect.entity_name)].append(effect)

            for entity, cur_effects in effects_split.items():
                entity_type, entity_name = entity
                if entity_type == EntityType.CHARACTER:
                    if entity_name == ch.name:
                        ch.apply_effects(cur_effects, events)
                    else:
                        with Character.load(entity_name) as other_ch:
                            other_ch.apply_effects(cur_effects, events)
                elif entity_type == EntityType.PROJECT_STAGE:
                    with ProjectStage.load(entity_name) as stage:
                        stage.apply_effects(cur_effects, events)
                else:
                    raise Exception(
                        f"Unexpected entity in effect: {entity_type} {entity_name}"
                    )

            if ch.acted_this_turn() and not ch.encounters:
                self._finish_turn(ch, events)
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

    # translate the results of the encounter into absolute modifications
    def _compute_encounter_effects(
        self, ch: Character, encounter: Encounter, actions: EncounterActions
    ) -> List[Effect]:
        rolls = self._replay_actions(ch, encounter, actions)
        if actions.flee:
            return []

        ret = []

        if encounter.card.checks:
            ocs = defaultdict(int)
            failures = 0

            for idx, check in enumerate(encounter.card.checks):
                if rolls[idx] >= check.target_number:
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

        if actions.choices:
            ret.extend(encounter.card.choices.benefit)
            ret.extend(
                dataclasses.replace(ct, is_cost=True)
                for ct in encounter.card.choices.cost
            )
        for choice_idx, cnt in actions.choices.items():
            choice = encounter.card.choices.choice_list[choice_idx]
            for _ in range(cnt):
                ret.extend(choice.benefit)
                ret.extend(dataclasses.replace(ct, is_cost=True) for ct in choice.cost)
        return ret

    # note this does update luck as well as validating stuff
    def _replay_actions(
        self, ch: Character, encounter: Encounter, actions: EncounterActions
    ) -> List[int]:
        rolls = list(encounter.rolls[:])

        if encounter.card.checks:
            # validate the actions by rerunning them
            for adj in actions.adjusts or []:
                ch.spend_luck(1, "adjust")
                rolls[adj] += 1

            for from_c, to_c in actions.transfers or []:
                if rolls[from_c] < 2:
                    raise BadStateException("From not enough for transfer")
                rolls[from_c] -= 2
                rolls[to_c] += 1

            if actions.flee:
                ch.spend_luck(1, "flee")

            rolls = tuple(rolls)
            if (ch.luck, rolls) != (actions.luck, actions.rolls):
                raise BadStateException("Computed luck/rolls doesn't match?")

        if encounter.card.choices:
            choices = encounter.card.choices
            if choices.is_random:
                rnd = defaultdict(int)
                for v in encounter.rolls:
                    rnd[v - 1] += 1
                if rnd != actions.choices:
                    raise BadStateException(
                        f"Choice should match roll for random ({rnd}, {actions.choices})"
                    )
            tot = 0
            for choice_idx, cnt in actions.choices.items():
                if choice_idx < 0 or choice_idx >= len(choices.choice_list):
                    raise BadStateException(f"Choice out of range: {choice_idx}")
                choice = choices.choice_list[choice_idx]
                tot += cnt
                if cnt < choice.min_choices:
                    raise IllegalMoveException(
                        f"Must choose {choice.name or 'this'} at least {with_s(choice.min_choices, 'time')}."
                    )
                if cnt > choice.max_choices:
                    raise IllegalMoveException(
                        f"Must choose {choice.name or 'this'} at most {with_s(choice.max_choices, 'time')}."
                    )
            if tot < choices.min_choices:
                raise IllegalMoveException(
                    f"Must select at least {with_s(choices.min_choices, 'choice')}."
                )
            if tot > choices.max_choices:
                raise IllegalMoveException(
                    f"Must select at most {with_s(choices.max_choices, 'choice')}."
                )
        elif actions.choices:
            raise BadStateException("Choices not allowed here.")

        return rolls

    # currently we assume nothing in here adds to the current list of events,
    # to avoid confusing the player when additional stuff shows up in the
    # outcome, but there's probably nothing strictly wrong if it did
    def _finish_turn(self, ch: Character, events: List[Event]) -> None:
        self._bad_reputation_check(ch)
        if ch.encounters:
            return

        self._discard_resources(ch)
        if ch.encounters:
            return

        with ProjectStage.load_for_character(ch.name) as current:
            for cur in current:
                cur.apply_effects(
                    [
                        Effect(
                            EffectType.TIME_PASSES,
                            1,
                        )
                    ],
                    events,
                )

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
        overage = sum(ch.resources.values()) - ch.get_max_resources()
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
                        ),
                        max_choices=cnt,
                    )
                    for rs, cnt in ch.resources.items()
                    if cnt > 0
                ],
            ),
        )
        ch.queue_template(discard_template, context_type=EncounterContextType.SYSTEM)
