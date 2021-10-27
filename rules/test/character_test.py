import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from typing import Any, Dict, List, Optional
from unittest import main

from picaro.common.exceptions import IllegalMoveException
from picaro.rules.base import get_rules_cache
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.internal import (
    Character,
    Effect,
    EffectType,
    Filter,
    FilterType,
    Overlay,
    OverlayType,
    Route,
    RouteType,
    Trigger,
    TriggerType,
)


class CharacterTest(FlatworldTestBase):
    def test_get_skill_rank(self) -> None:
        expected_ranks = [
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
        ]
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            for xp, expected in expected_ranks:
                ch.skill_xp["Skill 1"] = xp
                actual = CharacterRules.get_skill_rank(ch, "Skill 1")
                self.assertEqual(expected, actual, msg=f"Calculating for {xp}")

    def test_overlays(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual(0, CharacterRules.get_skill_rank(ch, "Skill 3"))

        self._overlay_helper()
        self.assertEqual(1, CharacterRules.get_skill_rank(ch, "Skill 3"))

        self._overlay_helper(
            filters=[
                Filter(
                    type=FilterType.IN_COUNTRY,
                    subtype="Bravo",
                    value=None,
                ),
            ]
        )
        # Make sure they're in Alpha:
        BoardRules.move_token_for_entity(ch.uuid, "AF01", adjacent=False)
        self.assertEqual(1, CharacterRules.get_skill_rank(ch, "Skill 3"))
        # Then move to Bravo:
        BoardRules.move_token_for_entity(ch.uuid, "AF10", adjacent=False)
        self.assertEqual(2, CharacterRules.get_skill_rank(ch, "Skill 3"))

    def test_check_filters(self) -> None:
        skill_f = Filter(type=FilterType.SKILL_GTE, subtype="Skill 3", value=1)
        hex_f = Filter(type=FilterType.NEAR_HEX, subtype="AA04", value=2)
        cty_f = Filter(type=FilterType.IN_COUNTRY, subtype="Alpha", value=None)
        ncty_f = Filter(type=FilterType.NOT_IN_COUNTRY, subtype="Alpha", value=None)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            with self.assertRaises(IllegalMoveException):
                CharacterRules.check_filters(ch, [skill_f])
            ch.skill_xp["Skill 3"] = 20
            self.assertEqual(1, CharacterRules.get_skill_rank(ch, "Skill 3"))
            with self.assertNotRaises(IllegalMoveException):
                CharacterRules.check_filters(ch, [skill_f])
            ch.skill_xp["Skill 3"] = 50
            self.assertEqual(2, CharacterRules.get_skill_rank(ch, "Skill 3"))
            with self.assertNotRaises(IllegalMoveException):
                CharacterRules.check_filters(ch, [skill_f])

        ch = Character.load_by_name(self.CHARACTER)

        BoardRules.move_token_for_entity(ch.uuid, "AF10", adjacent=False)
        with self.assertRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [hex_f])
        BoardRules.move_token_for_entity(ch.uuid, "AA06", adjacent=False)
        with self.assertNotRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [hex_f])
        BoardRules.move_token_for_entity(ch.uuid, "AA04", adjacent=False)
        with self.assertNotRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [hex_f])

        BoardRules.move_token_for_entity(ch.uuid, "AF10", adjacent=False)
        with self.assertRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [cty_f])
        with self.assertNotRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [ncty_f])

        BoardRules.move_token_for_entity(ch.uuid, "AC03", adjacent=False)
        with self.assertNotRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [cty_f])
        with self.assertRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [ncty_f])

        with self.assertRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [cty_f, hex_f])
        BoardRules.move_token_for_entity(ch.uuid, "AA03", adjacent=False)
        with self.assertNotRaises(IllegalMoveException):
            CharacterRules.check_filters(ch, [cty_f, hex_f])

    def test_overlay_filters_worst_case(self) -> None:
        num_overlays = 10

        ch = Character.load_by_name(self.CHARACTER)
        for i in range(num_overlays):
            self._overlay_helper(
                value=1,
                filters=[Filter(type=FilterType.SKILL_GTE, subtype="Skill 3", value=i)]
                if i > 0
                else [],
            )

        # most don't apply because they're filtered on base rank
        self.assertEqual(1, CharacterRules.get_skill_rank(ch, "Skill 3"))

    def test_get_relevant_actions(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        BoardRules.move_token_for_entity(ch.uuid, "AE06", adjacent=False)

        r_global = Route(RouteType.GLOBAL, steps=[])
        r_unavail = Route(RouteType.UNAVAILABLE, steps=[])
        r_AE06 = Route(RouteType.NORMAL, steps=[])
        r_AD05 = Route(RouteType.NORMAL, steps=["AD05"])
        r_AE05 = Route(RouteType.NORMAL, steps=["AE05"])
        r_AD07 = Route(RouteType.NORMAL, steps=["AD07"])
        r_AE07 = Route(RouteType.NORMAL, steps=["AE07"])
        r_AE08 = Route(RouteType.NORMAL, steps=["AD07", "AE08"])

        filters_list = [
            ([], [r_global]),
            ([Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=0)], [r_global]),
            ([Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=1)], [r_unavail]),
            ([Filter(FilterType.NEAR_HEX, subtype="AE06", value=1)], [r_AE06]),
            ([Filter(FilterType.NEAR_HEX, subtype="AF06", value=1)], [r_AE06]),
            (
                [Filter(FilterType.IN_COUNTRY, subtype="Alpha", value=None)],
                [r_AD05, r_AE05],
            ),
            (
                [Filter(FilterType.NOT_IN_COUNTRY, subtype="Alpha", value=None)],
                [r_AE06],
            ),
            (
                [
                    Filter(FilterType.IN_COUNTRY, subtype="Bravo", value=None),
                    Filter(FilterType.NEAR_HEX, subtype="AE06", value=1),
                ],
                [r_AD07, r_AE07],
            ),
            (
                [
                    Filter(FilterType.IN_COUNTRY, subtype="Bravo", value=None),
                    Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=0),
                ],
                [r_AD07, r_AE07],
            ),
            (
                [
                    Filter(FilterType.IN_COUNTRY, subtype="Bravo", value=None),
                    Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=1),
                ],
                [r_unavail],
            ),
            (
                [
                    Filter(FilterType.NEAR_HEX, subtype="AD08", value=1),
                    Filter(FilterType.NEAR_HEX, subtype="AE09", value=1),
                ],
                [r_AE08],
            ),
        ]
        name_map = {f"Zap{i}": f for i, f in enumerate(filters_list)}
        for name, filters in name_map.items():
            self._action_helper(name, filters=filters[0])

        actions, routes = CharacterRules.get_relevant_actions(ch, radius=3)
        self.assertEqual(len(actions), len(filters_list))
        for action in actions:
            self.assertIn(
                routes[action.uuid],
                name_map[action.name][1],
                msg=str(name_map[action.name][0]),
            )

    def test_triggers(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AA08")
        self.assertEqual(len(effects), 0)

        self._trigger_helper(EffectType.MODIFY_COINS)
        self._trigger_helper(EffectType.MODIFY_SPEED, subtype="AA08")
        self._trigger_helper(EffectType.MODIFY_REPUTATION, subtype="AB10")
        self._trigger_helper(
            EffectType.MODIFY_LUCK,
            subtype="AC05",
            filters=[Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=1)],
        )
        self._trigger_helper(
            EffectType.MODIFY_HEALTH,
            subtype=None,
            filters=[Filter(FilterType.SKILL_GTE, subtype="Skill 3", value=1)],
        )

        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, None)
        self.assertEqual({e.type for e in effects}, {EffectType.MODIFY_COINS})
        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AA08")
        self.assertEqual(
            {e.type for e in effects},
            {EffectType.MODIFY_COINS, EffectType.MODIFY_SPEED},
        )
        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AB10")
        self.assertEqual(
            {e.type for e in effects},
            {EffectType.MODIFY_COINS, EffectType.MODIFY_REPUTATION},
        )
        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AC05")
        self.assertEqual({e.type for e in effects}, {EffectType.MODIFY_COINS})

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.skill_xp["Skill 3"] = 25
        self.assertEqual(1, CharacterRules.get_skill_rank(ch, "Skill 3"))

        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AB10")
        self.assertEqual(
            {e.type for e in effects},
            {
                EffectType.MODIFY_COINS,
                EffectType.MODIFY_REPUTATION,
                EffectType.MODIFY_HEALTH,
            },
        )
        effects = CharacterRules.run_triggers(ch, TriggerType.MOVE_HEX, "AC05")
        self.assertEqual(
            {e.type for e in effects},
            {EffectType.MODIFY_COINS, EffectType.MODIFY_LUCK, EffectType.MODIFY_HEALTH},
        )

    def test_find_promote_job(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(CharacterRules.find_promote_job(ch), "Red Job 2")
            CharacterRules.switch_job(ch, "Red Job 2")
            self.assertIsNone(CharacterRules.find_promote_job(ch))

    def test_find_demote_job(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(CharacterRules.find_demote_job(ch), "Green Job")
            CharacterRules.switch_job(ch, "Red Job 2")
            self.assertEqual(CharacterRules.find_demote_job(ch), "Red Job 1")

    def test_find_bad_job(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(CharacterRules.find_bad_job(ch), "Green Job")
            CharacterRules.switch_job(ch, "Red Job 2")
            self.assertEqual(CharacterRules.find_bad_job(ch), "Green Job")

    def _overlay_helper(self, value=1, filters: List[Filter] = []) -> None:
        self.add_overlay(
            type=OverlayType.SKILL_RANK,
            subtype="Skill 3",
            value=value,
            is_private=True,
            filters=filters,
        )

    def _trigger_helper(
        self,
        effect_type: EffectType,
        subtype: Optional[str] = None,
        filters: List[Filter] = [],
    ) -> None:
        self.add_trigger(
            name=None,
            type=TriggerType.MOVE_HEX,
            subtype=subtype,
            costs=[],
            effects=[Effect(type=effect_type, subtype=None, value=1)],
            is_private=True,
            filters=filters,
        )

    def _action_helper(self, name: str, filters: List[Filter] = []) -> None:
        self.add_trigger(
            name=name,
            type=TriggerType.ACTION,
            subtype=None,
            costs=[],
            effects=[],
            is_private=True,
            filters=filters,
        )


if __name__ == "__main__":
    main()
