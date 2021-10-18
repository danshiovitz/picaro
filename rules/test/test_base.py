import pathlib
import sys
from contextlib import nullcontext
from typing import Any, Dict, List, Optional
from unittest import TestCase

from picaro.common.storage import ConnectionManager
from picaro.rules.base import RulesManager
from picaro.rules.game import GameRules
from picaro.rules.test.gen_flat import generate_flatworld


class FlatworldTestBase(TestCase):
    PLAYER_UUID = "testplayer"
    OTHER_PLAYER_UUID = "testplayer"
    CHARACTER = "Alice"
    OTHER_CHARACTER = "Bob"

    def setUp(self) -> None:
        self.maxDiff = None
        ConnectionManager.initialize(db_path=None)
        with ConnectionManager(game_uuid=None, player_uuid=self.PLAYER_UUID):
            data = generate_flatworld()
            game = GameRules.create_game(data)
        self.connection_manager = ConnectionManager(
            game_uuid=game.uuid, player_uuid=self.PLAYER_UUID
        )
        self.connection_manager.__enter__()

        self.rules_manager = RulesManager(self.CHARACTER)
        self.rules_manager.__enter__()

        GameRules.add_character(self.CHARACTER, self.PLAYER_UUID, "Red Job 1", "AG04")
        GameRules.add_character(
            self.OTHER_CHARACTER, self.OTHER_PLAYER_UUID, "Blue Job", "AB02"
        )

    def tearDown(self) -> None:
        self.rules_manager.__exit__(None, None, None)
        self.rules_manager = None
        self.connection_manager.__exit__(None, None, None)
        self.connection_manager = None

    def assertNotRaises(self, excls) -> None:
        # dummy thing basically for parity with assertRaises, does nothing
        return nullcontext()
