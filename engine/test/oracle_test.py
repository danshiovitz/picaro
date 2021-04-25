import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main

from picaro.engine.exceptions import IllegalMoveException
from picaro.engine.oracle import Oracle
from picaro.engine.storage import ConnectionManager, with_connection
from picaro.engine.types import Effect, EffectType, Event, OracleStatus


class OracleTest(TestCase):
    def setUp(self):
        ConnectionManager.initialize(db_path=None)
        self.session_ctx = ConnectionManager(player_id=100, game_id=1)
        self.session_ctx.__enter__()

        def session_cleanup():
            self.session_ctx.__exit__(None, None, None)
            self.session_ctx = None
            ConnectionManager.MEMORY_CONNECTION_HANDLE = None

        self.addCleanup(session_cleanup)

    def test_basic(self) -> None:
        oracle_id = Oracle.create("Conan", "Mighty and all-knowing oracle, where did I leave my car keys?")
        with Oracle.load(oracle_id) as oracle:
            with self.assertRaises(IllegalMoveException):
                oracle.answer("Conan", "Mortal, you should look beneath thy couch", [Effect(type=EffectType.MODIFY_HEALTH, value=-3)])
        with Oracle.load(oracle_id) as oracle:
            oracle.answer("Thor", "Mortal, you should look beneath thy couch", [Effect(type=EffectType.MODIFY_HEALTH, value=-3)])
        with Oracle.load(oracle_id) as oracle:
            with self.assertRaises(IllegalMoveException):
                oracle.finish("Thor", confirm=True)
        with Oracle.load(oracle_id) as oracle:
            oracle.finish("Conan", confirm=True)


if __name__ == "__main__":
    main()
