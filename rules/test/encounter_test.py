import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from collections import defaultdict
from typing import Any, Dict, List, Optional
from unittest import main

from picaro.common.exceptions import IllegalMoveException
from picaro.rules.base import get_rules_cache
from picaro.rules.character import CharacterRules
from picaro.rules.encounter import EncounterRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.internal import (
    Challenge,
    Character,
    Choices,
    Choice,
    Effect,
    EffectType,
    EncounterCheck,
    EncounterContextType,
    FullCard,
    FullCardType,
    Gadget,
    Outcome,
    Overlay,
    OverlayType,
    TemplateCard,
    TemplateCardType,
)


class EncounterTest(FlatworldTestBase):
    def test_reify_card_challenge(self) -> None:
        template = TemplateCard(
            name=f"Test Card",
            desc="...",
            type=TemplateCardType.CHALLENGE,
            data=Challenge(
                skills=["Skill 4", "Skill 5", "Skill 6"],
                rewards=[Outcome.GAIN_HEALING, Outcome.GAIN_RESOURCES],
                penalties=[Outcome.LOSE_COINS, Outcome.LOSE_RESOURCES],
            ),
        )
        skill_cnts = defaultdict(int)
        reward_cnts = defaultdict(int)
        penalty_cnts = defaultdict(int)
        tn_cnts = defaultdict(int)
        for _ in range(800):
            card = EncounterRules.reify_card(
                template, ["Skill 1", "Skill 2", "Skill 3"], 3, EncounterContextType.JOB
            )
            for check in card.data:
                skill_cnts[check.skill] += 1
                reward_cnts[check.reward] += 1
                penalty_cnts[check.penalty] += 1
                tn_cnts[check.target_number] += 1

        skills = sorted(skill_cnts.keys(), key=lambda v: -skill_cnts[v])
        self.assertEqual(len(skills), 20)
        self.assertEqual(set(skills[0:6]), {f"Skill {i+1}" for i in range(6)})

        rewards = sorted(reward_cnts.keys(), key=lambda v: -reward_cnts[v])
        self.assertEqual(
            set(rewards[0:4]),
            {
                Outcome.GAIN_HEALING,
                Outcome.GAIN_RESOURCES,
                Outcome.GAIN_COINS,
                Outcome.GAIN_REPUTATION,
            },
        )

        penalties = sorted(penalty_cnts.keys(), key=lambda v: -penalty_cnts[v])
        self.assertEqual(
            set(penalties[0:3]),
            {Outcome.DAMAGE, Outcome.LOSE_COINS, Outcome.LOSE_RESOURCES},
        )

        tns = sorted(tn_cnts.keys(), key=lambda v: -tn_cnts[v])
        self.assertEqual(tns[0], 7)
        self.assertEqual(set(tns[1:3]), {6, 8})
        self.assertEqual(set(tns[3:7]), {5, 9, 4, 10})

    def test_reify_card_choice(self) -> None:
        template = TemplateCard(
            name=f"Test Card",
            desc="...",
            type=TemplateCardType.CHOICE,
            data=Choices(
                min_choices=0,
                max_choices=1,
                choice_list=[Choice(), Choice()],
            ),
        )
        card = EncounterRules.reify_card(template, [], 1, EncounterContextType.JOB)
        self.assertEqual(len(card.data.choice_list), 2)

        template = TemplateCard(
            name=f"Test Card",
            desc="...",
            type=TemplateCardType.CHOICE,
            data=Choices(
                min_choices=0,
                max_choices=-1,
                choice_list=[Choice(), Choice()],
            ),
        )
        card = EncounterRules.reify_card(template, [], 1, EncounterContextType.JOB)
        self.assertEqual(len(card.data.choice_list), 1)

    def test_reify_card_special(self) -> None:
        template = TemplateCard(
            name=f"Test Card",
            desc="...",
            type=TemplateCardType.SPECIAL,
            data="xyzzy",
        )
        EncounterRules.reify_card(template, [], 1, EncounterContextType.JOB)

    def test_make_encounter_challenge(self) -> None:
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.CHALLENGE,
            data=[
                EncounterCheck(
                    skill=s,
                    target_number=5,
                    reward=Outcome.GAIN_COINS,
                    penalty=Outcome.LOSE_COINS,
                )
                for s in ["Skill 1", "Skill 2", "Skill 3"]
            ],
            signs=["Zodiac 1", "Zodiac 2"],
        )

        ch = Character.load_by_name(self.CHARACTER)
        self._make_skill_boost(ch)

        rolls = defaultdict(int)
        orig_rolls = defaultdict(int)
        for _ in range(800):
            enc = EncounterRules.make_encounter(ch, card)
            self.assertEqual(len(enc.rolls), 3)
            for idx, vals in enumerate(enc.rolls):
                rolls[(idx, vals[-1])] += 1
                orig_rolls[(idx, vals[0])] += 1

        # skill 1 has no bonus, so we expect 1-8
        vals = {r[1]: v for r, v in rolls.items() if r[0] == 0}
        self.assertEqual(len(vals), 8)
        for r, cnt in vals.items():
            self.assertIn(r, {1, 2, 3, 4, 5, 6, 7, 8})
            self.assertGreaterEqual(cnt, 70)

        # skill 2 has a +2 bonus, so we expect 3-10
        vals = {r[1]: v for r, v in rolls.items() if r[0] == 1}
        self.assertEqual(len(vals), 8)
        for r, cnt in vals.items():
            self.assertIn(r, {3, 4, 5, 6, 7, 8, 9, 10})
            self.assertGreaterEqual(cnt, 75)

        # skill 3 has a +2 bonus and reliable skill, so we expect 3-10,
        # but 3 and 4 should be much less common
        vals = {r[1]: v for r, v in rolls.items() if r[0] == 2}
        self.assertEqual(len(vals), 8)
        for r, cnt in vals.items():
            self.assertIn(r, {3, 4, 5, 6, 7, 8, 9, 10})
            if r in (3, 4):
                self.assertGreaterEqual(cnt, 10)
                self.assertLessEqual(cnt, 40)
            else:
                self.assertGreaterEqual(cnt, 90)

        # but original rolls should be normally across 3-10
        vals = {r[1]: v for r, v in orig_rolls.items() if r[0] == 1}
        self.assertEqual(len(vals), 8)
        for r, cnt in vals.items():
            self.assertIn(r, {3, 4, 5, 6, 7, 8, 9, 10})
            self.assertGreaterEqual(cnt, 75)

    def _make_skill_boost(self, ch: Character) -> None:
        guuid = Gadget.create(
            uuid="",
            name="Skill Certificate",
            desc=None,
            entity=ch.uuid,
            triggers=[],
            overlays=[],
            actions=[],
        )
        with Gadget.load_for_write(guuid) as gadget:
            gadget.add_overlay_object(
                Overlay(
                    uuid="",
                    type=OverlayType.SKILL_RANK,
                    subtype="Skill 2",
                    value=2,
                    is_private=True,
                    filters=[],
                )
            )
            gadget.add_overlay_object(
                Overlay(
                    uuid="",
                    type=OverlayType.SKILL_RANK,
                    subtype="Skill 3",
                    value=2,
                    is_private=True,
                    filters=[],
                )
            )
            gadget.add_overlay_object(
                Overlay(
                    uuid="",
                    type=OverlayType.RELIABLE_SKILL,
                    subtype="Skill 3",
                    value=2,
                    is_private=True,
                    filters=[],
                )
            )
        get_rules_cache().overlays.clear()

    def test_make_encounter_choice(self) -> None:
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.CHOICE,
            data=Choices(
                min_choices=0,
                max_choices=1,
                choice_list=[Choice(), Choice()],
            ),
            signs=["Zodiac 1", "Zodiac 2"],
        )
        ch = Character.load_by_name(self.CHARACTER)
        EncounterRules.make_encounter(ch, card)

    def test_make_encounter_special_trade(self) -> None:
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.SPECIAL,
            data="trade",
            signs=["Zodiac 1", "Zodiac 2"],
        )
        ch = Character.load_by_name(self.CHARACTER)
        EncounterRules.make_encounter(ch, card)

    def test_convert_outcome(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        card = FullCard(
            uuid="",
            name=f"Test Card",
            desc="...",
            type=FullCardType.CHALLENGE,
            data=[
                EncounterCheck(
                    skill=s,
                    target_number=5,
                    reward=Outcome.GAIN_COINS,
                    penalty=Outcome.LOSE_COINS,
                )
                for s in ["Skill 1", "Skill 2", "Skill 3"]
            ],
            signs=["Zodiac 1", "Zodiac 2"],
        )
        for outcome in Outcome:
            effects = EncounterRules.convert_outcome(outcome, 2, ch, card)
            if outcome == Outcome.NOTHING:
                self.assertEqual(len(effects), 0, msg=str(outcome))
            else:
                self.assertGreaterEqual(len(effects), 1, msg=str(outcome))


if __name__ == "__main__":
    main()
