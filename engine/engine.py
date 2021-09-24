import dataclasses
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.utils import with_s

from .board import create_board, load_board
from .character import Character, TurnFlags
from .deck import create_decks
from .exceptions import BadStateException, IllegalMoveException
from .game import create_game, load_game
from .job import Job, create_jobs, load_jobs
from .oracle import Oracle
from .project import Project, Task
from .snapshot import (
    Board as snapshot_Board,
    Character as snapshot_Character,
    CreateGameData,
    Hex as snapshot_Hex,
    Oracle as snapshot_Oracle,
    Project as snapshot_Project,
    Token as snapshot_Token,
)
from .storage import ConnectionManager, with_connection
from .types import (
    Action,
    Choice,
    Choices,
    Country,
    Effect,
    EffectType,
    Encounter,
    EncounterActions,
    EncounterCheck,
    EncounterContextType,
    Outcome,
    EntityType,
    FullCardType,
    Record,
    TemplateCard,
    TemplateCardType,
)


class Engine:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)

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
            ch.apply_regardless(
                [
                    Effect(type=EffectType.MODIFY_COINS, value=50),
                    Effect(type=EffectType.MODIFY_RESOURCES, value=10),
                ],
                [],
            )

        project_name = "Quest for Sandwiches"
        Project.create(project_name, "Monument", loc)
        with Project.load(project_name) as proj:
            from .types import TaskType

            proj.add_task(TaskType.CHALLENGE)

        with Task.load(project_name + " Task 1") as task:
            task.start(character_name, [])

    @with_connection()
    def create_game(self, data: CreateGameData, *, player_id: int) -> int:
        game = create_game(
            name=data.name,
            skills=data.skills,
            resources=data.resources,
            project_types=data.project_types,
            zodiacs=data.zodiacs,
        )
        ConnectionManager.fix_game_id(game.id)
        # now that game id is fixed we can call this:
        create_board(hexes=data.hexes, tokens=data.tokens, countries=data.countries)
        create_jobs(data.jobs)
        create_decks(data.template_decks)
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
        with Project.load_in_progress() as projects:
            snapshots = (p.get_snapshot(character_name, include_all) for p in projects)
            return [s for s in snapshots if include_all or s.tasks]

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
    def start_task(
        self,
        task_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Task.load(task_name) as task:
            with Character.load(character_name) as ch:
                with Task.load_for_character(character_name) as current:
                    if len(current) >= ch.get_max_tasks():
                        raise IllegalMoveException(
                            "You are already at your maximum number of active tasks."
                        )

                # other requirements could be checked here

                records: List[Record] = []
                ch.apply_bargain(task.cost, records)

                # if it's a challenge card, we discard a bunch of cards to refresh the
                # deck faster, and get to the point where we're rebuilding the deck with
                # challenge cards sooner
                if task.type == TaskType.CHALLENGE:
                    ch.discard_job_cards(6)

                task.start(ch.name, records)
                return records

    @with_connection()
    def return_task(
        self,
        task_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Task.load(task_name) as task:
            with Character.load(character_name) as ch:
                records: List[Record] = []
                task.do_return(ch.name, records)
                return records

    @with_connection()
    def get_skills(
        self, *, player_id: int, game_id: int, character_name: str
    ) -> List[str]:
        return load_game().skills

    @with_connection()
    def get_jobs(
        self, *, player_id: int, game_id: int, character_name: str
    ) -> List[Job]:
        return load_jobs()

    @with_connection()
    def get_oracles(
        self, free: bool, *, player_id: int, game_id: int, character_name: str
    ) -> List[snapshot_Oracle]:
        if free:
            with Oracle.load_unassigned(character_name) as unassigned:
                return [o.get_snapshot() for o in unassigned]
        else:
            with Oracle.load_for_petitioner(
                character_name
            ) as pet_projects, Oracle.load_for_granter(
                character_name
            ) as grant_projects:
                return [o.get_snapshot() for o in pet_projects + grant_projects]

    @with_connection()
    def get_oracle_cost(
        self,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Choices:
        with Character.load(character_name) as ch:
            return self._get_oracle_cost(ch)

    def _get_oracle_cost(self, ch: Character) -> Choices:
        rss = {rs for rs, v in ch.resources.items() if v > 0}
        choices = Choices(
            min_choices=1,
            max_choices=1,
            is_random=False,
            choice_list=tuple(
                Choice(
                    cost=(
                        Effect(type=EffectType.MODIFY_RESOURCES, subtype=rs, value=-1),
                    )
                )
                for rs in rss
            ),
        )
        return choices

    @with_connection()
    def create_oracle(
        self,
        request: str,
        payment_selections: Dict[int, int],
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Tuple[str, Sequence[Record]]:
        with Character.load(character_name) as ch:
            with Oracle.load_for_petitioner(ch.name) as current:
                if len(current) >= ch.get_max_oracles():
                    raise IllegalMoveException(
                        "You are already at your maximum number of active oracle requests."
                    )

            records: List[Record] = []
            occ = self._get_oracle_cost(ch)
            payment = self._eval_choices(occ, [], payment_selections, records)
            ch.apply_bargain(payment, records)
            id = Oracle.create(ch.name, payment, request)
            return id, records

    @with_connection()
    def answer_oracle(
        self,
        oracle_id: str,
        response: str,
        proposal: List[Record],
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Oracle.load(oracle_id) as oracle:
            with Character.load(character_name) as ch:
                records: List[Record] = []
                oracle.answer(ch.name, response, proposal)
                return records

    @with_connection()
    def confirm_oracle(
        self,
        oracle_id: str,
        confirm: bool,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Oracle.load(oracle_id) as oracle:
            with Character.load(character_name) as ch:
                records: List[Record] = []
                if confirm:
                    ch.apply_bargain(oracle.proposal, records)
                    oracle.finish(ch.name, confirm=True)
                else:
                    oracle.finish(ch.name, confirm=False)
                return records

    @with_connection()
    def do_job(
        self, card_id: int, *, player_id: int, game_id: int, character_name: str
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            records: List[Record] = []
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_tableau_card(card_id)
            return records

    @with_connection()
    def token_action(
        self,
        token_name: str,
        action_name: str,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            records: List[Record] = []
            self._basic_action_prep(ch, consume_action=False)

            board = load_board()
            ch_location = board.get_token_location(ch.name)
            token_location = board.get_token_location(token_name)
            if ch_location != token_location:
                raise IllegalMoveException(
                    f"You must be in hex {token_location} to perform that action."
                )
            action, token_type, token_name = board.get_token_action(
                token_name, action_name
            )
            ch.apply_bargain(action.cost, records)
            ch.apply_regardless(action.benefit, records)
            return records

    @with_connection()
    def camp(
        self, player_id: int, game_id: int, character_name: str
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            records: List[Record] = []
            self._basic_action_prep(ch, consume_action=True)
            ch.queue_camp_card()
            return records

    @with_connection()
    def travel(
        self, step: str, *, player_id: int, game_id: int, character_name: str
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            self._travel_prep(ch)
            records: List[Record] = []
            ch.step(step, records)
            board = load_board()
            new_loc = board.get_token_location(ch.name)
            with Task.load_for_character(ch.name) as current:
                for cur in current:
                    cur.apply_regardless(
                        [
                            Effect(
                                EffectType.EXPLORE,
                                new_loc,
                            )
                        ],
                        records,
                    )
            ch.queue_travel_card(new_loc)
            return records

    @with_connection()
    def end_turn(
        self, *, player_id: int, game_id: int, character_name: str
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            records: List[Record] = []
            self._basic_action_prep(ch, consume_action=False)
            if not ch.has_encounters():
                self._finish_turn(ch, records)
            return records

    @with_connection()
    def resolve_encounter(
        self,
        actions: EncounterActions,
        *,
        player_id: int,
        game_id: int,
        character_name: str,
    ) -> Sequence[Record]:
        with Character.load(character_name) as ch:
            records: List[Record] = []

            if not ch.encounter:
                raise BadStateException("No encounter is currently active.")

            encounter = ch.encounter
            if encounter.card.type == FullCardType.CHALLENGE:
                effects = self._eval_challenge(
                    ch,
                    encounter.card.data,
                    encounter.rolls,
                    actions,
                    encounter.card.entity_type,
                    encounter.card.entity_name,
                    records,
                )
            elif encounter.card.type == FullCardType.CHOICE:
                effects = self._eval_choices(
                    encounter.card.data, encounter.rolls, actions.choices, records
                )
            else:
                raise Exception(f"Bad card type: {encounter.card.type.name}")

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
                        if encounter.card.context_type == EncounterContextType.ACTION:
                            ch.apply_bargain(cur_effects, records)
                        else:
                            ch.apply_regardless(cur_effects, records)
                    else:
                        with Character.load(entity_name) as other_ch:
                            other_ch.apply_regardless(cur_effects, records)
                elif entity_type == EntityType.TASK:
                    with Task.load(entity_name) as task:
                        task.apply_regardless(cur_effects, records)
                else:
                    raise Exception(
                        f"Unexpected entity in effect: {entity_type} {entity_name}"
                    )

            ch.encounter_finished()

            return records

    def _basic_action_prep(self, ch: Character, consume_action: bool) -> None:
        if ch.has_encounters():
            raise BadStateException("An encounter is currently active.")
        if consume_action:
            if not ch.check_set_flag(TurnFlags.ACTED):
                raise BadStateException("You have already acted this turn.")

    def _travel_prep(self, ch: Character) -> None:
        if ch.has_encounters():
            raise BadStateException("An encounter is currently active.")
        if ch.speed <= 0:
            raise IllegalMoveException(f"You have no remaining speed.")

    def _eval_challenge(
        self,
        ch: Character,
        checks: List[EncounterCheck],
        rolls: List[int],
        actions: EncounterActions,
        entity_type: Optional[str],
        entity_name: Optional[str],
        records: List[Record],
    ) -> List[Effect]:
        rolls = list(rolls[:])

        # validate the actions by rerunning them (note this also updates luck)
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

        if actions.flee:
            return []

        effects = []

        ocs = defaultdict(int)
        failures = 0

        for idx, check in enumerate(checks):
            if rolls[idx] >= check.target_number:
                ocs[check.reward] += 1
            else:
                ocs[check.penalty] += 1
                failures += 1

        mcs = defaultdict(int)

        sum_til = lambda v: (v * v + v) // 2
        for outcome, cnt in ocs.items():
            effects.extend(
                self._convert_outcome(
                    outcome, cnt, ch, checks[0].skill, entity_type, entity_name
                )
            )
        if failures > 0:
            effects.append(
                Effect(
                    type=EffectType.MODIFY_XP,
                    subtype=checks[0].skill,
                    value=failures,
                )
            )

        return effects

    def _convert_outcome(
        self,
        outcome: Outcome,
        cnt: int,
        ch: Character,
        default_skill: str,
        entity_type: Optional[str],
        entity_name: Optional[str],
    ) -> List[Effect]:
        sum_til = lambda v: (v * v + v) // 2
        if outcome == Outcome.GAIN_COINS:
            return [Effect(type=EffectType.MODIFY_COINS, value=sum_til(cnt))]
        elif outcome == Outcome.LOSE_COINS:
            return [Effect(type=EffectType.MODIFY_COINS, value=-cnt)]
        elif outcome == Outcome.GAIN_REPUTATION:
            return [Effect(type=EffectType.MODIFY_REPUTATION, value=sum_til(cnt))]
        elif outcome == Outcome.LOSE_REPUTATION:
            return [Effect(type=EffectType.MODIFY_REPUTATION, value=-cnt)]
        elif outcome == Outcome.GAIN_HEALING:
            return [Effect(type=EffectType.MODIFY_HEALTH, value=cnt * 3)]
        elif outcome == Outcome.DAMAGE:
            return [Effect(type=EffectType.MODIFY_HEALTH, value=-sum_til(cnt))]
        elif outcome == Outcome.GAIN_XP:
            return [
                Effect(type=EffectType.MODIFY_XP, subtype=default_skill, value=cnt * 5)
            ]
        elif outcome == Outcome.GAIN_RESOURCES:
            return [Effect(type=EffectType.MODIFY_RESOURCES, value=cnt)]
        elif outcome == Outcome.LOSE_RESOURCES:
            return [Effect(type=EffectType.MODIFY_RESOURCES, value=-cnt)]
        elif outcome == Outcome.GAIN_TURNS:
            return [Effect(type=EffectType.MODIFY_TURNS, value=cnt)]
        elif outcome == Outcome.LOSE_TURNS:
            return [Effect(type=EffectType.MODIFY_TURNS, value=-cnt)]
        elif outcome == Outcome.GAIN_SPEED:
            return [Effect(type=EffectType.MODIFY_SPEED, value=cnt * 2)]
        elif outcome == Outcome.LOSE_SPEED:
            return [Effect(type=EffectType.MODIFY_SPEED, value=-cnt)]
        elif outcome == Outcome.TRANSPORT:
            return [Effect(type=EffectType.TRANSPORT, value=cnt * 5)]
        elif outcome == Outcome.LOSE_LEADERSHIP:
            return [Effect(type=EffectType.LEADERSHIP, value=-cnt)]
        elif outcome == Outcome.GAIN_PROJECT_XP:
            use_name: Optional[str] = None
            if entity_type is not None and entity_type == EntityType.TASK:
                use_name = entity_name
            else:
                with Task.load_for_character(ch.name) as tasks:
                    if tasks:
                        task = random.choice(tasks)
                        use_name = task.name
            if use_name:
                return [
                    Effect(
                        entity_type=EntityType.TASK,
                        entity_name=use_name,
                        type=EffectType.MODIFY_XP,
                        value=cnt * 3,
                    )
                ]
            else:
                return []
        elif outcome == Outcome.NOTHING:
            return []
        else:
            raise Exception(f"Unknown effect: {outcome}")

    def _eval_choices(
        self,
        choices: Choices,
        rolls: List[int],
        selections: Dict[int, int],
        records: List[Record],
    ) -> List[Effect]:
        if choices.is_random:
            rnd = defaultdict(int)
            for v in rolls:
                rnd[v - 1] += 1
            if rnd != selections:
                raise BadStateException(
                    f"Choice should match roll for random ({rnd}, {selections})"
                )

        tot = 0
        for choice_idx, cnt in selections.items():
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

        effects: List[Effect] = []
        effects.extend(choices.benefit)
        effects.extend(choices.cost)
        for choice_idx, cnt in selections.items():
            choice = choices.choice_list[choice_idx]
            for _ in range(cnt):
                effects.extend(choice.benefit)
                effects.extend(choice.cost)
        return effects

    # currently we assume nothing in here adds to the current list of records,
    # to avoid confusing the player when additional stuff shows up in the
    # records, but there's probably nothing strictly wrong if it did
    def _finish_turn(self, ch: Character, records: List[Record]) -> None:
        self._bad_reputation_check(ch)
        if ch.has_encounters():
            return

        self._discard_resources(ch)
        if ch.has_encounters():
            return

        with Task.load_for_character(ch.name) as current:
            for cur in current:
                cur.apply_regardless(
                    [
                        Effect(
                            EffectType.TIME_PASSES,
                            1,
                        )
                    ],
                    records,
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
            type=TemplateCardType.CHOICE,
            data=Choices(
                min_choices=1,
                max_choices=1,
                is_random=False,
                choice_list=[
                    [
                        Choice(
                            benefit=(
                                Effect(
                                    type=EffectType.LEADERSHIP, subtype=None, value=-1
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
            type=TemplateCardType.CHOICE,
            data=Choices(
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
