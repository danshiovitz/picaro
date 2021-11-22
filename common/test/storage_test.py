import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest import TestCase, main

from picaro.common.exceptions import IllegalMoveException
from picaro.common.serializer import SubclassVariant
from picaro.common.storage import (
    ConnectionManager,
    StorageBase,
    StandardWrapper,
    data_subclass_of,
)


class Foo(StandardWrapper):
    class Data(StorageBase["Foo.Data"]):
        TABLE_NAME = "foo"
        uuid: str
        b: int
        c: str

    @classmethod
    def load_by_b(cls, b: int) -> List["Foo"]:
        return cls._load_helper(["b = :b"], {"b": b})


class Variant3(StandardWrapper):
    class Data(StorageBase["Variant3.Data"], SubclassVariant):
        TABLE_NAME = "variant"
        uuid: str
        type: str
        a: int
        z: int = 3


@data_subclass_of(Variant3.Data, ["x"])
class SubclassX(Variant3.Data):
    x: int
    y: int


@data_subclass_of(Variant3.Data, ["p"])
class SubclassP(Variant3.Data):
    p: str
    y: int


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

    def test_update(self):
        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            uuid = Foo.create(b=3, c="bagels")

        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            with Foo.load_for_write(uuid) as foo:
                foo.b = 7
            foo2 = Foo.load(uuid)
            self.assertEqual(foo.b, 7)

        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            foo2 = Foo.load(uuid)
            self.assertEqual(foo.b, 7)

        with self.assertRaises(IllegalMoveException):
            with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
                try:
                    with Foo.load_for_write(uuid) as foo:
                        foo.b = 10
                        raise IllegalMoveException("booo")
                finally:
                    foo2 = Foo.load(uuid)
                    self.assertEqual(foo2.b, 7)

        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            foo2 = Foo.load(uuid)
            self.assertEqual(foo2.b, 7)

    def test_roundtrip_subclass(self):
        f = Variant3.create_detached(uuid="fuff", type="x", a=3, x=4, y=5)
        with ConnectionManager(game_uuid="abc", player_uuid="xyz"):
            Variant3.insert([f])
            with Variant3.load_for_write(f.uuid) as g:
                self.assertEqual(g, f)
                g.a = 13
                g.x = 14
            h = Variant3.load(f.uuid)
            self.assertEqual(h.a, 13)
            self.assertEqual(h.x, 14)


if __name__ == "__main__":
    main()
