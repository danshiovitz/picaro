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
from picaro.engine.types import (
    Effect,
    EffectType,
    Emblem,
    EncounterContextType,
    Feat,
    HookType,
    JobType,
)


class CharacterTest(TestCase):
    def setUp(self):
        patcher = patch("picaro.engine.character.load_job")
        self.load_job_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.load_job_mock.return_value = self._make_job()

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
            ch.skill_xp["Foo"] = xp
            self.assertEqual(
                ch.get_skill_rank("Foo"), rank, f"Expected rank={rank} for xp={xp}"
            )

        ch.skill_xp["Foo"] = 70
        emblem = Emblem(
            name="Foo Boost",
            feats=[Feat(hook=HookType.SKILL_RANK, param="Foo", value=2)],
        )
        ch.emblems.append(emblem)
        self.assertEqual(ch.get_skill_rank("Foo"), 5)
        emblem = Emblem(
            name="Generic Boost",
            feats=[Feat(hook=HookType.SKILL_RANK, param=None, value=2)],
        )
        ch.emblems.append(emblem)
        self.assertEqual(ch.get_skill_rank("Foo"), 6)  # capped at 6

    def test_apply_effect_gain_coins(self) -> None:
        ch = self._make_ch()
        board = self._make_board()
        ch.coins = 3

        effects = [Effect(type=EffectType.GAIN_COINS, rank=1, param=None)]
        outcome = ch.apply_effects(effects, EncounterContextType.JOB, board)
        self.assertEqual(ch.coins, 4)
        assert outcome.coins is not None
        self.assertEqual(outcome.coins.old_val, 3)
        self.assertEqual(outcome.coins.new_val, 4)

        effects = [Effect(type=EffectType.GAIN_COINS, rank=4, param=None)]
        outcome = ch.apply_effects(effects, EncounterContextType.JOB, board)
        self.assertEqual(ch.coins, 14)
        assert outcome.coins is not None
        self.assertEqual(outcome.coins.old_val, 4)
        self.assertEqual(outcome.coins.new_val, 14)

    def test_speed_hook(self) -> None:
        ch = self._make_ch()
        self.assertEqual(ch.get_init_speed(), 3)
        self.load_job_mock.assert_called()

        emblem = Emblem(
            name="Speed Boost",
            feats=[Feat(hook=HookType.INIT_SPEED, param=None, value=2)],
        )
        ch.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 5)

        emblem = Emblem(
            name="Speed Penalty",
            feats=[Feat(hook=HookType.INIT_SPEED, param=None, value=-4)],
        )
        ch.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 1)

        emblem = Emblem(
            name="Speed Penalty",
            feats=[Feat(hook=HookType.INIT_SPEED, param=None, value=-3)],
        )
        ch.emblems.append(emblem)
        self.assertEqual(ch.get_init_speed(), 0)

        ch.emblems.pop()
        ch.emblems.pop()
        self.assertEqual(ch.get_init_speed(), 5)

        self.load_job_mock.return_value = self._make_job(type=JobType.LACKEY)
        self.assertEqual(ch.get_init_speed(), 0)

    def _make_ch(self) -> Character:
        return Character.create(name="Test", player_id=100, job_name="Tester")

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
