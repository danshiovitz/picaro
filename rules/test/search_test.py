import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from typing import Any, Dict, List, Optional
from unittest import main

from picaro.common.exceptions import BadStateException
from picaro.rules.search import SearchRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.internal import Action, Character, Gadget


class SearchTest(FlatworldTestBase):
    def test_search_skills(self) -> None:
        actual = SearchRules.search_skills()
        self.assertEqual(len(actual), 20)

    def test_search_resources(self) -> None:
        actual = SearchRules.search_resources()
        self.assertEqual(len(actual), 5)

    def test_search_zodiacs(self) -> None:
        actual = SearchRules.search_zodiacs()
        self.assertEqual(len(actual), 12)

    def test_search_hexes(self) -> None:
        actual = SearchRules.search_hexes()
        self.assertEqual(len(actual), 121)

    def test_search_countries(self) -> None:
        actual = SearchRules.search_countries()
        self.assertEqual(len(actual), 2)

    def test_search_games(self) -> None:
        actual = SearchRules.search_games()
        self.assertEqual(len(actual), 1)
        actual = SearchRules.search_games(name="Flatworld")
        self.assertEqual(len(actual), 1)
        with self.assertRaises(BadStateException):
            actual = SearchRules.search_games(name="Roundworld")

    def test_search_jobs(self) -> None:
        actual = SearchRules.search_jobs()
        self.assertEqual(len(actual), 4)

    def test_search_entities(self) -> None:
        self._add_emblem()
        actual = SearchRules.search_entities(details=False)
        ch = [a for a in actual if a.name == self.CHARACTER][0]
        self.assertEqual(len(ch.gadgets), 0)
        self.assertEqual(len(actual), 5)
        actual = SearchRules.search_entities(details=True)
        ch = [a for a in actual if a.name == self.CHARACTER][0]
        self.assertEqual(len(ch.gadgets), 1)

    def test_search_characters(self) -> None:
        actual = SearchRules.search_characters()
        self.assertEqual(len(actual), 2)
        actual = SearchRules.search_characters(character_name=self.CHARACTER)
        self.assertEqual(len(actual), 1)

    def test_search_actions(self) -> None:
        actual = SearchRules.search_actions(self.CHARACTER)
        self.assertEqual(len(actual), 0)
        self._add_emblem()
        actual = SearchRules.search_actions(self.CHARACTER)
        self.assertEqual(len(actual), 1)

    def _add_emblem(self) -> str:
        ch = Character.load_by_name(self.CHARACTER)
        guuid = Gadget.create(
            uuid="",
            name="Thing-o-matic",
            desc=None,
            entity=ch.uuid,
            triggers=[],
            overlays=[],
            actions=[
                Action(
                    uuid="",
                    name="Thingo",
                    costs=[],
                    effects=[],
                    is_private=False,
                    filters=[],
                )
            ],
        )
        return guuid


if __name__ == "__main__":
    main()
