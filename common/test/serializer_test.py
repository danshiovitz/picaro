import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent.parent))

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional
from unittest import TestCase, main

from picaro.common.serializer import (
    HasAnyType,
    SubclassVariant,
    external_fields_for,
    subclass_of,
    serialize,
    deserialize,
)


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
class Variant(HasAnyType):
    ANY_TYPE_MAP = defaultdict(lambda: str, {"a": Foo})

    type: str
    val: Optional[Any]


@dataclass(frozen=True)
class Variant2(HasAnyType):
    TYPE_INDICATOR = "type2"
    ANY_TYPE_MAP = defaultdict(lambda: str)

    type2: str
    val: Optional[Any]


@external_fields_for(Variant2, ["a"])
class Foo2:
    a: str
    b: int
    c: str


@dataclass(frozen=True)
class Variant3(SubclassVariant):
    type: str
    a: int
    z: int = 3


@subclass_of(Variant3, ["x"])
class SubclassX(Variant3):
    x: int
    y: int


@subclass_of(Variant3, ["w"])
class SubclassW(SubclassX):
    w: int


@subclass_of(Variant3, ["p"])
class SubclassP(Variant3):
    p: str
    y: int


@dataclass(frozen=True)
class Holder:
    vars: List[Variant3]


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

    def test_roundtrip_variant2(self):
        v = Variant2(type2="b", val="hello")
        self.assertEqual(v, deserialize(serialize(v), Variant2))
        v = Variant2(type2="b", val=None)
        self.assertEqual(v, deserialize(serialize(v), Variant2))
        v = Variant2(type2="a", val=Foo2(a="cat", b=4, c="dogs"))
        self.assertEqual(v, deserialize(serialize(v), Variant2))
        v = Variant2(type2="a", val=None)
        self.assertEqual(v, deserialize(serialize(v), Variant2))

    def test_roundtrip_variant3(self):
        v = SubclassX(type="x", a=1, x=2, y=3)
        self.assertEqual(v, deserialize(serialize(v), Variant3))
        v = SubclassP(type="p", a=1, p="fish", y=3)
        self.assertEqual(v, deserialize(serialize(v), Variant3))
        v = SubclassW(type="w", a=1, x=5, y=6, w=7)
        self.assertEqual(v, deserialize(serialize(v), Variant3))
        h = Holder(
            vars=(
                SubclassX(type="x", a=1, x=2, y=3),
                SubclassP(type="p", a=1, p="fish", y=3),
            )
        )
        self.assertEqual(h, deserialize(serialize(h), Holder))


if __name__ == "__main__":
    main()
