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
    AmountOverlay as external_AmountOverlay,
    Entity as external_Entity,
    Title,
)
from picaro.rules.types.internal import (
    AddEntityEffect,
    AddTitleEffect,
    Character,
    Effect,
    EffectType,
    EnableEffect,
    EncounterEffect,
    Entity,
    EntityAmountEffect,
    EntityType,
    FullCard,
    FullCardType,
    JobEffect,
    LocationEffect,
    MessageEffect,
    Meter,
    MeterAmountEffect,
    OverlayType,
    RemoveEntityEffect,
    RemoveTitleEffect,
    ResourceAmountEffect,
    SkillAmountEffect,
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
        self.assertEqual(len(EffectType), 20)

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.coins, 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [
                SkillAmountEffect(type=EffectType.MODIFY_XP, skill="Skill 6", amount=10)
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.skill_xp.get("Skill 6", 0), 10)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [
                SkillAmountEffect(type=EffectType.MODIFY_XP, skill=None, amount=10)
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].name, "Assign XP")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EntityAmountEffect(type=EffectType.MODIFY_REPUTATION, amount=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.reputation, 8)  # because initial value was 3
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EntityAmountEffect(type=EffectType.MODIFY_HEALTH, amount=-5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.health, 15)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EntityAmountEffect(type=EffectType.MODIFY_TURNS, amount=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.remaining_turns, 25)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EntityAmountEffect(type=EffectType.MODIFY_SPEED, amount=2)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.speed, 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            self.assertNotIn(TurnFlags.ACTED, ch.turn_flags)
            effects = [EnableEffect(type=EffectType.MODIFY_ACTIVITY, enable=False)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertIn(TurnFlags.ACTED, ch.turn_flags)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EnableEffect(type=EffectType.MODIFY_ACTIVITY, enable=True)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertNotIn(TurnFlags.ACTED, ch.turn_flags)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            effects = [EntityAmountEffect(type=EffectType.MODIFY_LUCK, amount=2)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.luck, 7)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_modify_resources(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [
                ResourceAmountEffect(
                    type=EffectType.MODIFY_RESOURCES, resource="Resource C", amount=5
                ),
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.resources, {"Resource C": 5})
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            # not worrying about exact draws, but we should end up with a
            # couple resources
            effects = [
                ResourceAmountEffect(
                    type=EffectType.MODIFY_RESOURCES, resource=None, amount=50
                )
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.resources), 5)
            self.assertEqual(len(records), 6, msg=str([r._data for r in records]))

    def test_apply_effects_add_remove_entity(self) -> None:
        overlay = external_AmountOverlay(
            uuid="",
            type=OverlayType.MAX_LUCK,
            is_private=False,
            filters=[],
            amount=1,
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
                    meters=[],
                ),
            ],
            locations=["AB05"],
            uuid="",
        )
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [AddEntityEffect(type=EffectType.ADD_ENTITY, entity=entity)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_max_luck(ch), 6)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

        entity_uuid = Entity.load_by_name(entity.name).uuid
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [
                RemoveEntityEffect(
                    type=EffectType.REMOVE_ENTITY, entity_uuid=entity_uuid
                )
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_max_luck(ch), 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_add_remove_title(self) -> None:
        overlay = external_AmountOverlay(
            uuid="",
            type=OverlayType.INIT_SPEED,
            is_private=True,
            filters=[],
            amount=2,
        )
        title = Title(
            name="Sir Kicks-a-lot",
            overlays=[overlay],
            triggers=[],
            actions=[],
            meters=[],
        )
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [AddTitleEffect(type=EffectType.ADD_TITLE, title=title)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_init_speed(ch), 5)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [
                RemoveTitleEffect(type=EffectType.REMOVE_TITLE, title=title.name)
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(CharacterRules.get_init_speed(ch), 3)
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
                EncounterEffect(type=EffectType.QUEUE_ENCOUNTER, encounter=template)
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
        effects = [LocationEffect(type=EffectType.MODIFY_LOCATION, hex="AG10")]
        records = []
        GameRules.apply_effects(ch, [], effects, records)
        self.assertEqual(BoardRules.get_single_token_hex(ch.uuid).name, "AG10")
        self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_modify_job(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            self.assertEqual(ch.job_name, "Red Job 1")
            effects = [JobEffect(type=EffectType.MODIFY_JOB, job_name="Blue Job")]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(ch.job_name, "Blue Job")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_end_game(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [MessageEffect(type=EffectType.END_GAME, message="Game over!")]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].data, "Game over!")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_leadership(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [EntityAmountEffect(type=EffectType.LEADERSHIP, amount=-1)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(ch.queued[0].name, "Leadership Challenge")
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_transport(self) -> None:
        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [EntityAmountEffect(type=EffectType.TRANSPORT, amount=5)]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

    def test_apply_effects_tick_meter(self) -> None:
        muuid = self.add_meter(
            name="Some Meter",
            min_value=0,
            max_value=10,
            cur_value=5,
            empty_effects=[EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=3)],
            full_effects=[EntityAmountEffect(type=EffectType.MODIFY_LUCK, amount=4)],
        )

        with Character.load_by_name_for_write(self.CHARACTER) as ch:
            effects = [
                MeterAmountEffect(
                    type=EffectType.TICK_METER,
                    entity_uuid=self.CH_UUID,
                    meter_uuid=muuid,
                    amount=3,
                )
            ]

            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(Meter.load(muuid).cur_value, 8)
            self.assertEqual(len(ch.queued), 0)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))

            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(Meter.load(muuid).cur_value, 10)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))
            self.assertEqual(ch.queued[0].name, "Meter Full")
            self.assertEqual(
                ch.queued[0].data.choice_list[0].effects[0].type, EffectType.MODIFY_LUCK
            )
            ch.queued = []

            effects = [
                MeterAmountEffect(
                    type=EffectType.TICK_METER,
                    entity_uuid=self.CH_UUID,
                    meter_uuid=muuid,
                    amount=-10,
                )
            ]
            records = []
            GameRules.apply_effects(ch, [], effects, records)
            self.assertEqual(Meter.load(muuid).cur_value, 0)
            self.assertEqual(len(ch.queued), 1)
            self.assertEqual(len(records), 1, msg=str([r._data for r in records]))
            self.assertEqual(ch.queued[0].name, "Meter Empty")
            self.assertEqual(
                ch.queued[0].data.choice_list[0].effects[0].type,
                EffectType.MODIFY_COINS,
            )

    def test_apply_effects_costs(self) -> None:
        costs = [
            EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=-5),
            EntityAmountEffect(type=EffectType.MODIFY_REPUTATION, amount=3),
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
