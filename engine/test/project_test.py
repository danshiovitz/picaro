import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main
from unittest.mock import Mock, patch

from picaro.engine.board import ActiveBoard
from picaro.engine.project import (
    Project,
    ProjectStage,
    ProjectStageType,
    ProjectStageStatus,
    ProjectTypeStorage,
)
from picaro.engine.storage import ConnectionManager, with_connection


class ProjectTest(TestCase):
    def setUp(self):
        board_patcher = patch("picaro.engine.project.load_board")
        self.load_board_mock = board_patcher.start()
        self.addCleanup(board_patcher.stop)

        ConnectionManager.initialize(db_path=None)
        self.session_ctx = ConnectionManager(player_id=100, game_id=1)
        self.session_ctx.__enter__()
        ProjectTypeStorage.insert_initial_data(pathlib.Path(__file__).absolute().parent.parent / "data")


        def session_cleanup():
            self.session_ctx.__exit__(None, None, None)
            self.session_ctx = None
            ConnectionManager.MEMORY_CONNECTION_HANDLE = None

        self.addCleanup(session_cleanup)

    def test_create_project(self) -> None:
        Project.create("Operation Meatloaf", "Monument", "BE12")
        with Project.load("Operation Meatloaf") as proj:
            proj.add_stage(ProjectStageType.WAITING)
        with ProjectStage.load("Operation Meatloaf", 1) as stage:
            self.assertEqual(stage.status, ProjectStageStatus.PENDING)

    def _make_board(self) -> ActiveBoard:
        return cast(ActiveBoard, Mock(spec=ActiveBoard))


if __name__ == "__main__":
    main()
