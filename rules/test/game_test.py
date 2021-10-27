import dataclasses
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from collections import defaultdict
from typing import Any, Dict, List, Optional
from unittest import main

from picaro.common.exceptions import IllegalMoveException
from picaro.rules.board import BoardRules
from picaro.rules.character import CharacterRules
from picaro.rules.game import GameRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.external import (
    Entity as external_Entity,
    Title,
    Overlay as external_Overlay,
)
from picaro.rules.types.internal import (
    Character,
    Effect,
    EffectType,
    EntityType,
    FullCard,
    FullCardType,
    OverlayType,
    TemplateCard,
    TemplateCardType,
    TurnFlags,
)


class GameTest(FlatworldTestBase):
    def test_start_season(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.remaining_turns = 10
            ch.luck = 3
            GameRules.start_season(ch, [])
            self.assertEqual(ch.remaining_turns, 20)
            self.assertEqual(ch.luck, 5)

    def test_start_turn(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.speed = 1
            ch.check_set_flag(TurnFlags.BAD_REP_CHECKED)
            ch.tableau = []
            GameRules.start_turn(ch, [])
            self.assertEqual(ch.speed, 3)
            self.assertEqual(ch.turn_flags, set())
            self.assertEqual(len(ch.tableau), 3)

    def test_end_turn(self) -> None:
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.SPECIAL,
            data="trade",
            signs=["Zodiac 1", "Zodiac 2"],
        )

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.reputation = 0
            GameRules.end_turn(ch, [])
            self.assertIsNotNone(ch.encounter)
            self.assertEqual(ch.encounter.card.name, "Bad Reputation")
            self.assertEqual(ch.remaining_turns, 20)
            ch.encounter = None
            # Bad reputation check happens only once a turn:
            GameRules.end_turn(ch, [])
            self.assertIsNone(ch.encounter)
            self.assertEqual(ch.remaining_turns, 19)
            ch.reputation = 10
            ch.remaining_turns = 20

            ch.resources = {"Resource A1": 100}
            GameRules.end_turn(ch, [])
            self.assertIsNotNone(ch.encounter)
            self.assertEqual(ch.encounter.card.name, "Discard Resources")
            self.assertEqual(ch.remaining_turns, 20)
            ch.encounter = None
            ch.resources = {}

            # empty out the tableau and refill it
            ch.tableau = []
            GameRules.start_turn(ch, [])
            # set one up to age out
            ch.tableau[1] = dataclasses.replace(ch.tableau[1], age=1)
            GameRules.end_turn(ch, [])
            self.assertEqual(ch.remaining_turns, 19)
            # see, it aged out and was replaced:
            self.assertEqual([t.age for t in ch.tableau], [2, 2, 3])

    def test_end_season(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            GameRules.end_season(ch, [])

    def test_intra_turn(self) -> None:
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.SPECIAL,
            data="trade",
            signs=["Zodiac 1", "Zodiac 2"],
        )

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.queued.append(card)
            GameRules.intra_turn(ch, [])
            self.assertIsNotNone(ch.encounter)
            self.assertEqual(ch.encounter.card.name, "Test Card")

    def test_apply_effects(self) -> None:
        # not sure how to force we have total coverage other than this:
        self.assertEqual(len(EffectType), 16)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [Effect(type=EffectType.MODIFY_COINS, subtype=None, value=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.coins, 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_XP, subtype="Skill 6", value=10)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.skill_xp.get("Skill 6", 0), 10)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_XP, subtype=None, value=10)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].name, "Assign XP")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_REPUTATION, subtype=None, value=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.reputation, 8)  # because initial value was 3
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_HEALTH, subtype=None, value=-5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.health, 15)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_TURNS, subtype=None, value=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.remaining_turns, 25)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_SPEED, subtype=None, value=2)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.speed, 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            self.assertNotIn(TurnFlags.ACTED, ch.turn_flags)
            effects = [Effect(type=EffectType.MODIFY_ACTIVITY, subtype=None, value=-1)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertIn(TurnFlags.ACTED, ch.turn_flags)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_ACTIVITY, subtype=None, value=1)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertNotIn(TurnFlags.ACTED, ch.turn_flags)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [Effect(type=EffectType.MODIFY_LUCK, subtype=None, value=2)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.luck, 7)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_modify_resources(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [
                Effect(type=EffectType.MODIFY_RESOURCES, subtype="Resource C", value=5)
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.resources, {"Resource C": 5})
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            # not worrying about exact draws, but we should end up with a
            # couple resources
            effects = [Effect(type=EffectType.MODIFY_RESOURCES, subtype=None, value=50)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.resources), 5)
            self.assertEqual(len(records), 6, msg=str([r._data for r in records]))

    def test_apply_effects_add_entity(self) -> None:
        overlay = external_Overlay(
            uuid="",
            type=OverlayType.MAX_LUCK,
            subtype=None,
            is_private=False,
            filters=[],
            value=1,
        )
        entity = external_Entity(
            type=EntityType.LANDMARK,
            subtype=None,
            name="Giant Clover",
            titles=[
                Title(
                    name=None,
                    overlays=[overlay],
                    triggers=[],
                    actions=[],
                ),
            ],
            locations=["AB05"],
            uuid="",
        )
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [Effect(type=EffectType.ADD_ENTITY, subtype=None, value=entity)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_max_luck(ch), 6)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_add_title(self) -> None:
        overlay = external_Overlay(
            uuid="",
            type=OverlayType.INIT_SPEED,
            subtype=None,
            is_private=True,
            filters=[],
            value=2,
        )
        title = Title(
            name="Sir Kicks-a-lot", overlays=[overlay], triggers=[], actions=[]
        )
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [Effect(type=EffectType.ADD_TITLE, subtype=None, value=title)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_init_speed(ch), 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_queue_encounter(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            template = TemplateCard(
                name=f"Test Card",
                desc="...",
                type=TemplateCardType.SPECIAL,
                data="trade",
            )

            effects = [
                Effect(type=EffectType.QUEUE_ENCOUNTER, subtype=None, value=template)
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].name, "Test Card")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_modify_location(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)

        BoardRules.move_token_for_entity(ch.uuid, "AA03", adjacent=False)
        self.assertEqual(BoardRules.get_single_token_hex(ch.uuid).name, "AA03")
        effects = [Effect(type=EffectType.MODIFY_LOCATION, subtype=None, value="AG10")]
        records = []
        GameRules.apply_effects(ch, [], effects, records)
        self.assertEqual(BoardRules.get_single_token_hex(ch.uuid).name, "AG10")
        self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_modify_job(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(ch.job_name, "Red Job 1")
            effects = [
                Effect(type=EffectType.MODIFY_JOB, subtype=None, value="Blue Job")
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.job_name, "Blue Job")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_leadership(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [Effect(type=EffectType.LEADERSHIP, subtype=None, value=-1)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].name, "Leadership Challenge")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_transport(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [Effect(type=EffectType.TRANSPORT, subtype=None, value=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_costs(self) -> None:
        costs = [
            Effect(type=EffectType.MODIFY_COINS, subtype=None, value=-5),
            Effect(type=EffectType.MODIFY_REPUTATION, subtype=None, value=3),
        ]

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.coins = 2
            ch.reputation = 0

        with self.assertRaises(IllegalMoveException):
            GameRules.apply_effects(ch, costs, [], [])

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(ch.coins, 2)
            self.assertEqual(ch.reputation, 0)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            ch.coins = 10
            ch.reputation = 0

        with self.assertNotRaises(IllegalMoveException):
            with Character.load_by_name_for_write(self.CHARACTER) as ch:
                GameRules.apply_effects(ch, costs, [], [])

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(ch.coins, 5)
            self.assertEqual(ch.reputation, 3)


if __name__ == "__main__":
    main()
