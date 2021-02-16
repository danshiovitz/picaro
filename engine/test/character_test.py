import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Dict, List
from unittest import TestCase, main
from unittest.mock import Mock

from picaro.engine.board import ActiveBoard
from picaro.engine.character import Character
from picaro.engine.types import Effect, EffectType, EncounterContextType


class CharacterTest(TestCase):
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

    def test_apply_effect_gain_coins(self) -> None:
        ch = self._make_ch()
        board = self._make_board()
        ch.coins = 3

        effects = [Effect(type=EffectType.GAIN_COINS, rank=1, param=None)]
        outcome = ch.apply_effects(effects, EncounterContextType.JOB, None, board)
        self.assertEqual(ch.coins, 4)
        self.assertIsNotNone(outcome.coins)
        self.assertEqual(outcome.coins.old_val, 3)
        self.assertEqual(outcome.coins.new_val, 4)

        effects = [Effect(type=EffectType.GAIN_COINS, rank=4, param=None)]
        outcome = ch.apply_effects(effects, EncounterContextType.JOB, None, board)
        self.assertEqual(ch.coins, 14)
        self.assertIsNotNone(outcome.coins)
        self.assertEqual(outcome.coins.old_val, 4)
        self.assertEqual(outcome.coins.new_val, 14)

    def _make_ch(self) -> Character:
        return Character(
            name="Test",
            player_id=100,
            job_name="Tester",
            skill_xp={},
            health=20,
            coins=0,
            resources=0,
            reputation=5,
            quest=0,
            remaining_turns=0,
            luck=0,
            tableau=[],
            encounters=[],
            job_deck=[],
            travel_deck=[],
            camp_deck=[],
            acted_this_turn=False,
        )

    def _make_board(self) -> ActiveBoard:
        return Mock(spec=ActiveBoard)


if __name__ == "__main__":
    main()
