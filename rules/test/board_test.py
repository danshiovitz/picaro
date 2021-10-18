import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from collections import defaultdict
from typing import Any, Dict, List, Optional
from unittest import main

from picaro.common.exceptions import IllegalMoveException
from picaro.rules.board import BoardRules
from picaro.rules.test.test_base import FlatworldTestBase
from picaro.rules.types.store import Character, Entity, Token


class BoardTest(FlatworldTestBase):
    def test_best_routes(self) -> None:
        all_expected = {
            "AA01": {
                "AA01": [],
                "AA05": ["AA02", "AA03", "AA04", "AA05"],
                "AC03": ["AB02", "AC02", "AC03"],
                "AE01": ["AB01", "AC01", "AD01", "AE01"],
                "AE05": ["AB02", "AC02", "AC03", "AD04", "AE04", "AE05"],
                "AK11": (
                    ["AB02", "AC02", "AC03", "AD04", "AE04", "AE05", "AF06", "AG06"]
                    + ["AG07", "AH08", "AI08", "AI09", "AJ10", "AK10", "AK11"]
                ),
                "AB01": ["AB01"],
            },
            "AA05": {
                "AA01": ["AA04", "AA03", "AA02", "AA01"],
                "AA05": [],
                "AC03": ["AB04", "AC04", "AC03"],
                "AE01": ["AB04", "AC04", "AC03", "AD02", "AE02", "AE01"],
                "AE05": ["AB05", "AC05", "AD05", "AE05"],
            },
            "AC03": {
                "AA01": ["AC02", "AB02", "AA01"],
                "AA05": ["AC04", "AB04", "AA05"],
                "AC03": [],
                "AE01": ["AD02", "AE02", "AE01"],
                "AE05": ["AD04", "AE04", "AE05"],
            },
            "AE01": {
                "AA01": ["AD01", "AC01", "AB01", "AA01"],
                "AA05": ["AE02", "AD02", "AC03", "AC04", "AB04", "AA05"],
                "AC03": ["AE02", "AD02", "AC03"],
                "AE01": [],
                "AE05": ["AE02", "AE03", "AE04", "AE05"],
            },
            "AE05": {
                "AA01": ["AE04", "AD04", "AC03", "AC02", "AB02", "AA01"],
                "AA05": ["AD05", "AC05", "AB05", "AA05"],
                "AC03": ["AE04", "AD04", "AC03"],
                "AE01": ["AE04", "AE03", "AE02", "AE01"],
                "AE05": [],
            },
        }

        for start, expected in all_expected.items():
            ends = list(expected.keys())
            actual = BoardRules.best_routes(start, ends)
            self.assertEqual(actual, expected)

    def test_min_distance_from_entity(self) -> None:
        entity = Entity.load_by_name("Alpha City")
        dist = BoardRules.min_distance_from_entity(entity.uuid, "AA08")
        self.assertEqual(dist, 7)
        Token.create(entity=entity.uuid, location="AA10")
        dist = BoardRules.min_distance_from_entity(entity.uuid, "AA08")
        self.assertEqual(dist, 2)

    def test_distance(self) -> None:
        all_expected = {
            "AA01": {
                "AA01": 0,
                "AA05": 4,
                "AC03": 3,
                "AE01": 4,
                "AE05": 6,
                "AK11": 15,
                "AB01": 1,
            },
            "AA05": {
                "AA01": 4,
                "AA05": 0,
                "AC03": 3,
                "AE01": 6,
                "AE05": 4,
            },
            "AC03": {
                "AA01": 3,
                "AA05": 3,
                "AC03": 0,
                "AE01": 3,
                "AE05": 3,
            },
            "AE01": {
                "AA01": 4,
                "AA05": 6,
                "AC03": 3,
                "AE01": 0,
                "AE05": 4,
            },
            "AE05": {
                "AA01": 6,
                "AA05": 4,
                "AC03": 3,
                "AE01": 4,
                "AE05": 0,
            },
        }

        for start, distances in all_expected.items():
            for end, expected in distances.items():
                actual = BoardRules.distance(start, end)
                self.assertEqual(actual, expected)

    def test_get_single_token_hex(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        hx = BoardRules.get_single_token_hex(ch.uuid)
        self.assertEqual("AG04", hx.name)

    def test_get_random_hex(self) -> None:
        hx = BoardRules.get_random_hex()
        self.assertEqual(len(hx.name), 4)

    def test_find_entity_neighbors(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)

        BoardRules.move_token_for_entity(ch.uuid, "AA01", adjacent=False)
        nghs = BoardRules.find_entity_neighbors(ch.uuid, 1, 1)
        self.assertEqual({n.name for n in nghs}, {"AA02", "AB01", "AB02"})

        BoardRules.move_token_for_entity(ch.uuid, "AA03", adjacent=False)
        nghs = BoardRules.find_entity_neighbors(ch.uuid, 1, 1)
        self.assertEqual(
            {n.name for n in nghs}, {"AA02", "AB02", "AB03", "AB04", "AA04"}
        )

        BoardRules.move_token_for_entity(ch.uuid, "AF06", adjacent=False)
        nghs = BoardRules.find_entity_neighbors(ch.uuid, 0, 2)
        self.assertEqual(len(nghs), 19)
        # should be in sorted order by distance:
        self.assertEqual({n.name for n in nghs[0:1]}, {"AF06"})
        self.assertEqual(
            {n.name for n in nghs[1:7]},
            {"AE06", "AE05", "AG06", "AE07", "AF07", "AF05"},
        )
        self.assertEqual(
            {n.name for n in nghs[7:19]},
            (
                {"AG07", "AF04", "AF08", "AH06", "AD06", "AG08"}
                | {"AD05", "AG04", "AG05", "AE04", "AD07", "AE08"}
            ),
        )

    def test_move_token_for_entity(self) -> None:
        ch = Character.load_by_name(self.CHARACTER)
        self.assertEqual("AG04", Token.load_single_by_entity(ch.uuid).location)
        BoardRules.move_token_for_entity(ch.uuid, "AD06", adjacent=False)
        self.assertEqual("AD06", Token.load_single_by_entity(ch.uuid).location)
        BoardRules.move_token_for_entity(ch.uuid, "AD07", adjacent=True)
        self.assertEqual("AD07", Token.load_single_by_entity(ch.uuid).location)
        with self.assertRaises(IllegalMoveException):
            BoardRules.move_token_for_entity(ch.uuid, "AA07", adjacent=True)

    def test_draw_resource_card(self) -> None:
        cnts = defaultdict(int)
        for _ in range(100):
            card = BoardRules.draw_resource_card("AA02")
            if card.value > 0:
                cnts[card.type] += card.value
        rs = list(cnts.keys())
        rs.sort(key=lambda r: -cnts[r])
        self.assertEqual(len(rs), 5)
        self.assertEqual(rs[0], "Resource A1")
        self.assertEqual(rs[1], "Resource A2")
        self.assertEqual(
            {rs[2], rs[3], rs[4]}, {"Resource B1", "Resource B2", "Resource C"}
        )


if __name__ == "__main__":
    main()
