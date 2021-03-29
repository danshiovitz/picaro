import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main
from unittest.mock import Mock, patch

from picaro.engine.board import load_board
from picaro.engine.exceptions import IllegalMoveException
from picaro.engine.project import (
    Project,
    ProjectStage,
    ProjectStageType,
    ProjectStageStatus,
    ProjectTypeStorage,
)
from picaro.engine.storage import ConnectionManager, with_connection
from picaro.engine.types import Event


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

    def test_waiting_stage(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_stage(ProjectStageType.WAITING)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.xp, 0)
            events: List[Event] = []
            stage.turn_finished(events)
            self.assertEqual(stage.xp, 1)
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.max_xp, 25)
            for _ in range(100):
                stage.turn_finished(events)
            self.assertEqual(stage.extra.turns_waited, 101)
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

    def test_resource_stage(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_stage(ProjectStageType.RESOURCE, resources=["Stone", "Timber"])

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.xp, 0)
            events: List[Event] = []
            stage.resource_delivered("Stone", events)
            self.assertEqual(stage.xp, 5)
            stage.resource_delivered("Stone", events)
            self.assertEqual(stage.xp, 10)
            stage.resource_delivered("Timber", events)
            self.assertEqual(stage.xp, 15)
            with self.assertRaises(IllegalMoveException):
                stage.resource_delivered("Wine", events)
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.max_xp, 25)
            for _ in range(10):
                stage.resource_delivered("Timber", events)
            self.assertEqual(stage.extra.given_resources, {"Stone": 2, "Timber": 11})
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

    def test_discovery_stage(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_stage(ProjectStageType.DISCOVERY)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.xp, 0)
            events: List[Event] = []

            wrong_guesses = stage.extra.possible_hexes - set(stage.extra.secret_hex)
            possible_size = len(stage.extra.possible_hexes)

            for wrong in wrong_guesses:
                stage.hex_explored(wrong, events)
                self.assertEqual(stage.xp, 0)
                self.assertEqual(len(stage.extra.possible_hexes), possible_size - 1)
                self.assertEqual(stage.extra.explored_hexes, {wrong})
                self.assertEqual(events, [])
                break

            stage.hex_explored("ZZ11", events)
            self.assertEqual(stage.xp, 0)
            self.assertEqual(
                len(stage.extra.possible_hexes), possible_size - 1
            )  # did not decrement
            self.assertEqual(len(stage.extra.explored_hexes), 1)  # did not increment
            self.assertEqual(events, [])

            stage.hex_explored(stage.extra.secret_hex, events)
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(len(events), 1)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

    def test_modify_xp(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "AE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_stage(ProjectStageType.WAITING)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)
            self.assertEqual(stage.xp, 0)
            events: List[Event] = []

            stage.modify_xp(3, events)
            self.assertEqual(stage.xp, 3)
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)

            stage.modify_xp(-5, events)
            self.assertEqual(stage.xp, 0)
            self.assertEqual(stage.status, ProjectStageStatus.UNASSIGNED)

            self.assertEqual(stage.max_xp, 25)
            stage.modify_xp(25, events)
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)

        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.xp, stage.max_xp)
            self.assertEqual(stage.status, ProjectStageStatus.FINISHED)


if __name__ == "__main__":
    main()
