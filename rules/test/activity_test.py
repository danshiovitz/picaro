import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

import dataclasses
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from unittest import main

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.rules.activity import ActivityRules
from picaro.rules.base import get_rules_cache
from picaro.rules.board import BoardRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.external import EncounterCommands
from picaro.rules.types.internal import (
    Character,
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterCheck,
    EntityAmountEffect,
    Filter,
    FilterType,
    FullCard,
    FullCardType,
    HexFilter,
    Outcome,
    TemplateCard,
    TemplateCardType,
    TriggerType,
    TurnFlags,
)


class ActivityTest(FlatworldTestBase):
    def test_do_job(self) -> None:
        with self.assertRaises(BadStateException):
            ActivityRules.do_job(self.CHARACTER, "bogusid")

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            # bogus but it'll do for the check
            ch.encounter = Encounter(card=None, rolls=[])

        with self.assertRaises(BadStateException):
            ActivityRules.do_job(self.CHARACTER, ch.tableau[0].card.uuid)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.encounter = None
            ch.check_set_flag(TurnFlags.ACTED)

        with self.assertRaises(BadStateException):
            ActivityRules.do_job(self.CHARACTER, ch.tableau[0].card.uuid)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.turn_flags.clear()

        # wrong location
        ch = Character.load_by_name(self.CHARACTER)
        if ch.tableau[0].location == "AA01":
            BoardRules.move_token_for_entity(ch.uuid, "AA02", adjacent=False)
        else:
            BoardRules.move_token_for_entity(ch.uuid, "AA01", adjacent=False)

        with self.assertRaises(IllegalMoveException):
            ActivityRules.do_job(self.CHARACTER, ch.tableau[0].card.uuid)

        # right location - job ends up as the encounter
        BoardRules.move_token_for_entity(
            ch.uuid, ch.tableau[0].location, adjacent=False
        )
        expected = ch.tableau[0].card.name
        _records = ActivityRules.do_job(self.CHARACTER, ch.tableau[0].card.uuid)
        ch = Character.load_by_name(self.CHARACTER)
        self.assertIsNotNone(ch.encounter)
        self.assertEqual(ch.encounter.card.name, expected)

    def test_perform_action(self) -> None:
        with self.assertRaises(BadStateException):
            ActivityRules.perform_action(self.CHARACTER, "bogus.id")

        action_id = self._add_action()
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            # bogus but it'll do for the check
            ch.encounter = Encounter(card=None, rolls=[])

        with self.assertRaises(BadStateException):
            ActivityRules.perform_action(self.CHARACTER, action_id)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.encounter = None

        # wrong location
        BoardRules.move_token_for_entity(ch.uuid, "AA01", adjacent=False)
        with self.assertRaises(IllegalMoveException):
            ActivityRules.perform_action(self.CHARACTER, action_id)

        # right location - job ends up as the encounter
        BoardRules.move_token_for_entity(ch.uuid, "AF08", adjacent=False)
        expected = ch.tableau[0].card.name
        _records = ActivityRules.perform_action(self.CHARACTER, action_id)
        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual(ch.coins, 6)

    def _add_action(self) -> str:
        return self.add_trigger(
            name="Thingo",
            type=TriggerType.ACTION,
            costs=[],
            effects=[EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=6)],
            is_private=False,
            filters=[HexFilter(type=FilterType.NEAR_HEX, hex="AF08", distance=1)],
        )

    def test_camp(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            # bogus but it'll do for the check
            ch.encounter = Encounter(card=None, rolls=[])

        with self.assertRaises(BadStateException):
            ActivityRules.camp(self.CHARACTER)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.encounter = None

        _records = ActivityRules.camp(self.CHARACTER)

    def test_travel(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        BoardRules.move_token_for_entity(ch.uuid, "AC10", adjacent=False)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            # bogus but it'll do for the check
            ch.encounter = Encounter(card=None, rolls=[])

        with self.assertRaises(BadStateException):
            ActivityRules.travel(self.CHARACTER, "AC09")

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.encounter = None
            ch.speed = 0

        with self.assertRaises(IllegalMoveException):
            ActivityRules.travel(self.CHARACTER, "AC09")

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.speed = 3
            # for right now, disable travel encounters:
            ch.turn_flags.add(TurnFlags.HAD_TRAVEL_ENCOUNTER)

        with self.assertRaises(IllegalMoveException):
            ActivityRules.travel(self.CHARACTER, "AA02")

        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual(BoardRules.get_single_token_hex(ch.uuid).name, "AC10")
        _records = ActivityRules.travel(self.CHARACTER, "AC09")
        self.assertEqual(BoardRules.get_single_token_hex(ch.uuid).name, "AC09")

        self._add_trigger(ch, "AC10")
        records = ActivityRules.travel(self.CHARACTER, "AC10")
        self.assertEqual(len(records), 1)
        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual(ch.coins, 5)

        # we expect some but not all the time to get a travel encounter
        enc_cnt = 0
        for idx in range(40):
            with Character.load_by_name_for_write(self.CHARACTER) as ch:
                ch.speed = 3
                ch.turn_flags.clear()
                ch.encounter = None
            ActivityRules.travel(self.CHARACTER, "AC09" if idx % 2 == 0 else "AC10")
            ch = Character.load_by_name(self.CHARACTER)
            if ch.encounter:
                enc_cnt += 1
                self.assertIn(TurnFlags.HAD_TRAVEL_ENCOUNTER, ch.turn_flags)
            else:
                self.assertNotIn(TurnFlags.HAD_TRAVEL_ENCOUNTER, ch.turn_flags)
        self.assertGreaterEqual(enc_cnt, 2)

        # TODO: maybe run some stats on relative kinds of travel encounters,
        # maybe taking hex danger into account

    def _add_trigger(self, ch: Character, hex: str) -> None:
        self.add_trigger(
            name=None,
            type=TriggerType.ENTER_HEX,
            hex=hex,
            costs=[],
            effects=[EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=5)],
            is_private=False,
            filters=[],
        )

    def test_end_turn(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            # bogus but it'll do for the check
            ch.encounter = Encounter(card=None, rolls=[])

        with self.assertRaises(BadStateException):
            ActivityRules.end_turn(self.CHARACTER)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.encounter = None

        _records = ActivityRules.end_turn(self.CHARACTER)

    def test_resolve_encounter_challenge(self) -> None:
        # uuid mismatch:
        with self.assertRaises(BadStateException):
            self._challenge_helper(encounter_uuid="badid")

        # luck mismatch:
        with self.assertRaises(BadStateException):
            self._challenge_helper(flee=True, luck_spent=2)

        # roll mismatch:
        with self.assertRaises(BadStateException):
            self._challenge_helper(rolls=[1, 1, 1])

        # regular success/fail resolution:
        self._challenge_helper(results=[False, False, True])

        # adjusts:
        self._challenge_helper(
            adjusts=[0, 1], luck_spent=2, rolls=[5, 6, 7], results=[False, True, True]
        )

        # transfers:
        self._challenge_helper(
            transfers=[[2, 0], [2, 0], [2, 1]],
            rolls=[6, 6, 1],
            results=[True, True, False],
        )

        # luck overspend:
        with self.assertRaises(IllegalMoveException):
            self._challenge_helper(
                adjusts=[0, 0, 0, 0, 0, 0], luck_spent=6, rolls=[10, 5, 7]
            )

        # flee:
        self._challenge_helper(flee=True, luck_spent=1)

    def _challenge_helper(
        self,
        encounter_uuid="abcdefghikl",
        adjusts: List[int] = [],
        transfers: List[Tuple[int, int]] = [],
        flee=False,
        luck_spent=0,
        rolls: List[int] = [4, 5, 7],
        results: List[bool] = [False, False, True],
    ) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            card = FullCard(
                uuid="abcdefghikl",
                name=f"Test Card",
                desc="...",
                type=FullCardType.CHALLENGE,
                data=[
                    EncounterCheck(
                        skill="Skill 1",
                        modifier=None,
                        target_number=6,
                        reward=Outcome.GAIN_COINS,
                        penalty=Outcome.LOSE_COINS,
                    ),
                    EncounterCheck(
                        skill="Skill 2",
                        modifier=None,
                        target_number=6,
                        reward=Outcome.GAIN_REPUTATION,
                        penalty=Outcome.LOSE_REPUTATION,
                    ),
                    EncounterCheck(
                        skill="Skill 3",
                        modifier=None,
                        target_number=6,
                        reward=Outcome.GAIN_SPEED,
                        penalty=Outcome.LOSE_SPEED,
                    ),
                ],
                signs=["Zodiac 1", "Zodiac 2"],
            )
            ch.encounter = Encounter(card=card, rolls=[[4], [5], [7]])
            ch.coins = 10
            ch.reputation = 10
            ch.speed = 10
            ch.skill_xp = {}

        commands = EncounterCommands(
            encounter_uuid=encounter_uuid,
            adjusts=adjusts,
            transfers=transfers,
            flee=flee,
            luck_spent=luck_spent,
            rolls=rolls,
            choices={},
        )

        ActivityRules.resolve_encounter(self.CHARACTER, commands)

        ch = Character.load_by_name(self.CHARACTER)
        if not flee:
            self.assertEqual(ch.coins, 11 if results[0] else 9)
            self.assertEqual(ch.reputation, 11 if results[1] else 9)
            self.assertEqual(ch.speed, 12 if results[2] else 9)
            self.assertEqual(ch.skill_xp.get("Skill 1", 0), 3 - sum(results))
        else:
            self.assertEqual(ch.coins, 10)
            self.assertEqual(ch.reputation, 10)
            self.assertEqual(ch.speed, 10)
            self.assertEqual(ch.skill_xp.get("Skill 1", 0), 0)

    def test_resolve_encounter_choice(self) -> None:
        # uuid mismatch
        with self.assertRaises(BadStateException):
            self._choice_helper(encounter_uuid="badid")

        # basic single selections
        self._choice_helper(selections={0: 1}, result_cnts=[1, 0, 0, 1])
        self._choice_helper(selections={1: 1}, result_cnts=[0, 1, 0, 1])
        self._choice_helper(selections={2: 1}, result_cnts=[0, 0, 1, 1])

        # choosing too many
        with self.assertRaises(IllegalMoveException):
            self._choice_helper(selections={0: 2})

        # choosing too many even though overall max isn't violated
        with self.assertRaises(IllegalMoveException):
            self._choice_helper(selections={0: 2}, overall_mm=[0, 10])

        # choosing too many even though individual max isn't violated
        with self.assertRaises(IllegalMoveException):
            self._choice_helper(selections={0: 2}, item_mms=[[0, 10]] * 3)

        # complex choice combo
        self._choice_helper(
            selections={0: 2, 1: 3, 2: 5},
            overall_mm=[0, 10],
            item_mms=[[0, 10]] * 3,
            result_cnts=[2, 3, 5, 1],
        )

        # choosing nothing - overall costs/effects don't happen either
        self._choice_helper(
            selections={},
            result_cnts=[0, 0, 0, 0],
        )

    def _choice_helper(
        self,
        encounter_uuid="abcdefghikl",
        overall_mm: Tuple[int, int] = [0, 1],
        item_mms: List[Tuple[int, int]] = [[0, 1], [0, 1], [0, 1]],
        selections: Dict[int, int] = {},
        result_cnts: List[int] = [],
    ) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            types = [
                EffectType.MODIFY_SPEED,
                EffectType.MODIFY_COINS,
                EffectType.MODIFY_HEALTH,
                EffectType.MODIFY_REPUTATION,
            ]
            card = FullCard(
                uuid="abcdefghikl",
                name=f"Test Card",
                desc="...",
                type=FullCardType.CHOICE,
                data=Choices(
                    min_choices=overall_mm[0],
                    max_choices=overall_mm[1],
                    effects=[EntityAmountEffect(type=types.pop(0), amount=1)],
                    choice_list=[
                        Choice(
                            min_choices=mm[0],
                            max_choices=mm[1],
                            effects=[EntityAmountEffect(type=types.pop(0), amount=1)],
                        )
                        for mm in item_mms
                    ],
                ),
                signs=["Zodiac 1", "Zodiac 2"],
            )
            ch.encounter = Encounter(card=card, rolls=[])
            ch.speed = 10
            ch.coins = 10
            ch.health = 10
            ch.reputation = 10

        commands = EncounterCommands(
            encounter_uuid=encounter_uuid,
            adjusts=[],
            transfers=[],
            flee=False,
            luck_spent=0,
            rolls=[],
            choices=selections,
        )

        ActivityRules.resolve_encounter(self.CHARACTER, commands)
        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual(ch.coins - 10, result_cnts[0])
        self.assertEqual(ch.health - 10, result_cnts[1])
        self.assertEqual(ch.reputation - 10, result_cnts[2])
        self.assertEqual(ch.speed - 10, result_cnts[3])


if __name__ == "__main__":
    main()
