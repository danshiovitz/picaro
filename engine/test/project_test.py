import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main

from picaro.engine.board import load_board
from picaro.engine.exceptions import IllegalMoveException
from picaro.engine.project import (
    Project,
    Task,
    TaskType,
    TaskStatus,
    ProjectTypeStorage,
)
from picaro.engine.storage import ConnectionManager, with_connection
from picaro.engine.types import Effect, EffectType, Event


class ProjectTest(TestCase):
    def setUp(self):
        ConnectionManager.initialize(db_path=None)
        self.session_ctx = ConnectionManager(player_id=100, game_id=1)
        self.session_ctx.__enter__()
        ProjectTypeStorage.insert_initial_data(
            pathlib.Path(__file__).absolute().parent.parent / "data"
        )

        def session_cleanup():
            self.session_ctx.__exit__(None, None, None)
            self.session_ctx = None
            ConnectionManager.MEMORY_CONNECTION_HANDLE = None

        self.addCleanup(session_cleanup)

        board = load_board()
        board.generate_flat_map()

    def test_waiting_task(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_task(TaskType.WAITING)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.xp, 0)
            events: List[Event] = []
            task.apply_outcome([Effect(type=EffectType.TIME_PASSES, value=1)], events)
            self.assertEqual(task.xp, 1)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.max_xp, 25)
            for _ in range(100):
                task.apply_outcome(
                    [Effect(type=EffectType.TIME_PASSES, value=1)], events
                )
            self.assertEqual(task.extra.turns_waited, 101)
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

    def test_resource_task(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_task(TaskType.RESOURCE, resources=["Stone", "Timber"])

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.xp, 0)
            events: List[Event] = []
            task.apply_outcome(
                [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Stone", value=1)],
                events,
            )
            self.assertEqual(task.xp, 5)
            task.apply_outcome(
                [
                    Effect(type=EffectType.MODIFY_RESOURCES, subtype="Stone", value=2),
                    Effect(type=EffectType.MODIFY_RESOURCES, subtype="Timber", value=1),
                ],
                events,
            )
            self.assertEqual(task.xp, 20)
            with self.assertRaises(IllegalMoveException):
                task.apply_outcome(
                    [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Wine", value=1)],
                    events,
                )
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.max_xp, 25)
            task.apply_outcome(
                [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Timber", value=10)],
                events,
            )
            self.assertEqual(task.extra.given_resources, {"Stone": 3, "Timber": 11})
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

    def test_discovery_task(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_task(TaskType.DISCOVERY)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.xp, 0)
            events: List[Event] = []

            wrong_guesses = task.extra.possible_hexes - set(task.extra.secret_hex)
            possible_size = len(task.extra.possible_hexes)

            for wrong in wrong_guesses:
                task.apply_outcome(
                    [Effect(type=EffectType.EXPLORE, value=wrong)], events
                )
                self.assertEqual(task.xp, 0)
                self.assertEqual(len(task.extra.possible_hexes), possible_size - 1)
                self.assertEqual(task.extra.explored_hexes, {wrong})
                self.assertEqual(events, [])
                break

            task.apply_outcome([Effect(type=EffectType.EXPLORE, value="ZZ11")], events)
            self.assertEqual(task.xp, 0)
            self.assertEqual(
                len(task.extra.possible_hexes), possible_size - 1
            )  # did not decrement
            self.assertEqual(len(task.extra.explored_hexes), 1)  # did not increment
            self.assertEqual(events, [])

            task.apply_outcome(
                [Effect(type=EffectType.EXPLORE, value=task.extra.secret_hex)], events
            )
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(len(events), 1)
            self.assertEqual(task.status, TaskStatus.FINISHED)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

    def test_modify_xp(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_task(TaskType.WAITING)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.xp, 0)
            events: List[Event] = []

            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=3)], events)
            self.assertEqual(task.xp, 3)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)

            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=-5)], events)
            self.assertEqual(task.xp, 0)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)

            self.assertEqual(task.max_xp, 25)
            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=25)], events)
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)


if __name__ == "__main__":
    main()
