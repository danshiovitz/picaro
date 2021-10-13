import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest import TestCase, main

from picaro.common.storage import ConnectionManager, StorageBase, StandardWrapper


class Foo(StandardWrapper):
    class Data(StorageBase["Foo.Data"]):
        TABLE_NAME = "foo"
        uuid: str
        b: int
        c: str

    @classmethod
    def load_by_b(cls, b: int) -> List["Foo"]:
        return cls._load_helper(["b = :b"], {"b": b})


class StorageTest(TestCase):
    def setUp(self):
        self.maxDiff = None
        ConnectionManager.initialize(None)

    def test_roundtrip_simple(self):
        f = Foo.create_detached(uuid="fish", b=3, c="bagels")
        f2 = Foo.create_detached(uuid="cow", b=7, c="lox")
        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            Foo.insert([f, f2])
            fs = Foo.load_by_b(3)
            self.assertEqual(fs[0].uuid, f.uuid)
            self.assertEqual(fs, [f])


if __name__ == "__main__":
    main()
