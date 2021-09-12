import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.board import CreateBoardData, load_board
from picaro.engine.exceptions import IllegalMoveException
from picaro.engine.project import (
    Project,
    Task,
    TaskType,
    TaskStatus,
    ProjectTypeStorage,
)
from picaro.engine.snapshot import Hex, Token
from picaro.engine.storage import ConnectionManager, with_connection
from picaro.engine.types import Country, Effect, EffectType, EntityType, Record


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
        board.create(self.generate_flat_map())

    def generate_flat_map(self) -> CreateBoardData:
        hexes = []
        for r in range(30):
            for c in range(30):
                coord = OffsetCoordinate(row=r, column=c)
                hexes.append(
                    Hex(
                        name=coord.get_name(),
                        coordinate=coord,
                        terrain="Plains",
                        country="Alpha",
                        danger=2,
                    )
                )
        tokens = [
            Token(
                name="Capitol City",
                type=EntityType.CITY,
                location="AJ15",
                actions=[],
                route=[],
            ),
        ]
        countries = [
            Country(
                name="Alpha",
                capitol_hex="AJ15",
                resources=["Stone", "Timber"],
            ),
        ]

        return CreateBoardData(hexes=hexes, tokens=tokens, countries=countries)

    def test_waiting_task(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_task(TaskType.WAITING)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.xp, 0)
            records: List[Record] = []
            task.apply_outcome([Effect(type=EffectType.TIME_PASSES, value=1)], records)
            self.assertEqual(task.xp, 1)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.max_xp, 25)
            for _ in range(100):
                task.apply_outcome(
                    [Effect(type=EffectType.TIME_PASSES, value=1)], records
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
            records: List[Record] = []
            task.apply_outcome(
                [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Stone", value=1)],
                records,
            )
            self.assertEqual(task.xp, 5)
            task.apply_outcome(
                [
                    Effect(type=EffectType.MODIFY_RESOURCES, subtype="Stone", value=2),
                    Effect(type=EffectType.MODIFY_RESOURCES, subtype="Timber", value=1),
                ],
                records,
            )
            self.assertEqual(task.xp, 20)
            with self.assertRaises(IllegalMoveException):
                task.apply_outcome(
                    [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Wine", value=1)],
                    records,
                )
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)
            self.assertEqual(task.max_xp, 25)
            task.apply_outcome(
                [Effect(type=EffectType.MODIFY_RESOURCES, subtype="Timber", value=10)],
                records,
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
            records: List[Record] = []

            wrong_guesses = task.extra.possible_hexes - set(task.extra.secret_hex)
            possible_size = len(task.extra.possible_hexes)

            for wrong in wrong_guesses:
                task.apply_outcome(
                    [Effect(type=EffectType.EXPLORE, value=wrong)], records
                )
                self.assertEqual(task.xp, 0)
                self.assertEqual(len(task.extra.possible_hexes), possible_size - 1)
                self.assertEqual(task.extra.explored_hexes, {wrong})
                self.assertEqual(records, [])
                break

            task.apply_outcome([Effect(type=EffectType.EXPLORE, value="ZZ11")], records)
            self.assertEqual(task.xp, 0)
            self.assertEqual(
                len(task.extra.possible_hexes), possible_size - 1
            )  # did not decrement
            self.assertEqual(len(task.extra.explored_hexes), 1)  # did not increment
            self.assertEqual(records, [])

            task.apply_outcome(
                [Effect(type=EffectType.EXPLORE, value=task.extra.secret_hex)], records
            )
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(len(records), 1)
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
            records: List[Record] = []

            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=3)], records)
            self.assertEqual(task.xp, 3)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)

            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=-5)], records)
            self.assertEqual(task.xp, 0)
            self.assertEqual(task.status, TaskStatus.UNASSIGNED)

            self.assertEqual(task.max_xp, 25)
            task.apply_outcome([Effect(type=EffectType.MODIFY_XP, value=25)], records)
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)

        with Task.load("Operation Meatloaf Task 1") as task:
            self.assertEqual(task.xp, task.max_xp)
            self.assertEqual(task.status, TaskStatus.FINISHED)


if __name__ == "__main__":
    main()
