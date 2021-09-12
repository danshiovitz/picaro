import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List, cast
from unittest import TestCase, main
from unittest.mock import Mock, patch

from picaro.engine.board import ActiveBoard
from picaro.engine.character import Character
from picaro.engine.job import Job
from picaro.engine.storage import ConnectionManager, with_connection
from picaro.engine.types import (
    Effect,
    EffectType,
    EncounterContextType,
    Gadget,
    JobType,
    Rule,
    RuleType,
)


class CharacterTest(TestCase):
    def setUp(self):
        job_patcher = patch("picaro.engine.character.load_job")
        self.load_job_mock = job_patcher.start()
        self.addCleanup(job_patcher.stop)
        self.load_job_mock.return_value = self._make_job()
        board_patcher = patch("picaro.engine.character.load_board")
        self.load_board_mock = board_patcher.start()
        self.addCleanup(board_patcher.stop)

        ConnectionManager.initialize(db_path=None)
        self.session_ctx = ConnectionManager(player_id=100, game_id=1)
        self.session_ctx.__enter__()

        def session_cleanup():
            self.session_ctx.__exit__(None, None, None)
            self.session_ctx = None
            ConnectionManager.MEMORY_CONNECTION_HANDLE = None

        self.addCleanup(session_cleanup)

    def test_get_skill_rank(self) -> None:
        ch = self._make_ch()
        self.assertEqual(ch.get_skill_rank("Foo"), 0)
        xp_rank = [
            (0, 0),
            (5, 0),
            (10, 0),
            (15, 0),
            (20, 1),
            (25, 1),
            (30, 1),
            (35, 1),
            (40, 1),
            (45, 2),
            (50, 2),
            (55, 2),
            (60, 2),
            (65, 2),
            (70, 3),
            (75, 3),
            (80, 3),
            (85, 3),
            (90, 3),
            (95, 4),
            (100, 4),
            (105, 4),
            (110, 4),
            (115, 4),
            (120, 4),
            (125, 5),
            (130, 5),
            (135, 5),
        ]
        for xp, rank in xp_rank:
            ch._data.skill_xp["Foo"] = xp
            self.assertEqual(
                ch.get_skill_rank("Foo"), rank, f"Expected rank={rank} for xp={xp}"
            )

        ch._data.skill_xp["Foo"] = 70
        emblem = Gadget(
            name="Foo Boost",
            rules=[
                Rule(type=RuleType.SKILL_RANK, subtype="Foo", value=2),
            ],
        )
        ch._data.emblems.append(emblem)
        self.assertEqual(ch.get_skill_rank("Foo"), 5)
        emblem = Gadget(
            name="Generic Boost",
            rules=[
                Rule(type=RuleType.SKILL_RANK, subtype=None, value=2),
            ],
        )
        ch._data.emblems.append(emblem)
        self.assertEqual(ch.get_skill_rank("Foo"), 6)  # capped at 6

    def test_apply_effect_gain_coins(self) -> None:
        ch = self._make_ch()
        ch._data.coins = 3

        effects = [Effect(type=EffectType.MODIFY_COINS, value=1)]
        records = []
        outcome = ch.apply_outcome(effects, records)
        self.assertEqual(ch.coins, 4)
        ec = [e for e in records if e.type == EffectType.MODIFY_COINS]
        self.assertEqual(len(ec), 1)
        self.assertEqual(ec[0].old_value, 3)
        self.assertEqual(ec[0].new_value, 4)

        effects = [
            Effect(type=EffectType.MODIFY_COINS, value=6),
            Effect(type=EffectType.MODIFY_COINS, value=4),
        ]
        records = []
        outcome = ch.apply_outcome(effects, records)
        self.assertEqual(ch.coins, 14)
        ec = [e for e in records if e.type == EffectType.MODIFY_COINS]
        self.assertEqual(len(ec), 1)
        self.assertEqual(ec[0].old_value, 4)
        self.assertEqual(ec[0].new_value, 14)

    def test_apply_effect_gain_xp(self) -> None:
        ch = self._make_ch()

        effects = [
            Effect(type=EffectType.MODIFY_XP, subtype="Fishing", value=3),
            Effect(type=EffectType.MODIFY_XP, subtype="Fishing", value=1),
        ]
        records = []
        outcome = ch.apply_outcome(effects, records)
        ec = [e for e in records if e.type == EffectType.MODIFY_XP]
        self.assertEqual(len(ec), 1)
        self.assertEqual(ec[0].subtype, "Fishing")
        self.assertEqual(ec[0].old_value, 0)
        self.assertEqual(ec[0].new_value, 4)

    def test_speed_rule(self) -> None:
        ch = self._make_ch()
        self.assertEqual(ch.get_init_speed(), 3)
        self.load_job_mock.assert_called()

        emblem = Gadget(
            name="Speed Boost",
            rules=[
                Rule(type=RuleType.INIT_SPEED, subtype=None, value=2),
            ],
        )
        ch._data.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 5)

        emblem = Gadget(
            name="Speed Penalty",
            rules=[
                Rule(type=RuleType.INIT_SPEED, subtype=None, value=-4),
            ],
        )
        ch._data.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 1)

        emblem = Gadget(
            name="Speed Penalty",
            rules=[
                Rule(type=RuleType.INIT_SPEED, subtype=None, value=-3),
            ],
        )
        ch._data.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 0)

        ch._data.emblems.pop()
        ch._data.emblems.pop()
        self.assertEqual(ch.get_init_speed(), 5)

        self.load_job_mock.return_value = self._make_job(type=JobType.LACKEY)
        self.assertEqual(ch.get_init_speed(), 0)

    def _make_ch(self) -> Character:
        Character.create(name="Test", player_id=100, job_name="Tester", location="AA11")
        return Character.load("Test").__enter__()

    def _make_board(self) -> ActiveBoard:
        return cast(ActiveBoard, Mock(spec=ActiveBoard))

    def _make_job(self, **kwargs) -> Job:
        defaults = {
            "name": "Tester",
            "type": JobType.SOLO,
            "rank": 2,
            "promotions": [],
            "deck_name": "Tester",
            "encounter_distances": [0, 1, 2, 3],
        }
        defaults.update(kwargs)
        return Job(**defaults)


if __name__ == "__main__":
    main()
