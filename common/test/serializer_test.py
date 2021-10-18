import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional
from unittest import TestCase, main

from picaro.common.serializer import serialize, deserialize


@dataclass(frozen=True)
class Foo:
    a: str
    b: int
    c: str


class Beenum(Enum):
    BEE = enum_auto()
    WASP = enum_auto()
    HORNET = enum_auto()


@dataclass(frozen=True)
class Complex:
    some: Foo
    more: List[Foo]
    most: Dict[str, Foo]
    bee: Beenum


@dataclass(frozen=True)
class Variant:
    type: str
    val: Optional[Any]

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: str) -> type:
        if type_val == "a":
            return Foo
        else:
            return str


class SerializeTest(TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_roundtrip_simple(self):
        f = Foo(a="fish", b=3, c="bagels")
        txt = serialize(f)
        g = deserialize(txt, Foo)
        self.assertEqual(f, g)
        self.assertEqual(txt, '{"a": "fish", "b": 3, "c": "bagels"}')

    def test_roundtrip_complex(self):
        f1 = Foo(a="fish", b=3, c="bagels")
        f2 = Foo(a="cat", b=7, c="sandwiches")
        f3 = Foo(a="dog", b=5, c="hot dogs")
        c = Complex(some=f1, more=(f2, f3), most={f1.a: f1, f3.a: f3}, bee=Beenum.WASP)
        txt = serialize(c)
        g = deserialize(txt, Complex)
        self.assertEqual(c, g)
        self.assertEqual(
            txt,
            '{"some": {"a": "fish", "b": 3, "c": "bagels"}, "more": [{"a": "cat", "b": 7, "c": "sandwiches"}, {"a": "dog", "b": 5, "c": "hot dogs"}], "most": {"fish": {"a": "fish", "b": 3, "c": "bagels"}, "dog": {"a": "dog", "b": 5, "c": "hot dogs"}}, "bee": "WASP"}',
        )

    def test_roundtrip_variant(self):
        v = Variant(type="b", val="hello")
        self.assertEqual(v, deserialize(serialize(v), Variant))
        v = Variant(type="b", val=None)
        self.assertEqual(v, deserialize(serialize(v), Variant))
        v = Variant(type="a", val=Foo(a="cat", b=4, c="dogs"))
        self.assertEqual(v, deserialize(serialize(v), Variant))
        v = Variant(type="a", val=None)
        self.assertEqual(v, deserialize(serialize(v), Variant))


if __name__ == "__main__":
    main()
