import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent))

from dataclasses import dataclass
from typing import Dict, List
from unittest import TestCase, main

from serializer import serialize, deserialize


@dataclass(frozen=True)
class Foo:
    a: str
    b: int
    c: str


@dataclass(frozen=True)
class Complex:
    some: Foo
    more: List[Foo]
    most: Dict[str, Foo]


class SerializeTest(TestCase):
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
        c = Complex(some=f1, more=[f2, f3], most={f1.a: f1, f3.a: f3})
        txt = serialize(c)
        g = deserialize(txt, Complex)
        self.assertEqual(c, g)
        self.assertEqual(
            txt,
            '{"some": {"a": "fish", "b": 3, "c": "bagels"}, "more": [{"a": "cat", "b": 7, "c": "sandwiches"}, {"a": "dog", "b": 5, "c": "hot dogs"}], "most": {"fish": {"a": "fish", "b": 3, "c": "bagels"}, "dog": {"a": "dog", "b": 5, "c": "hot dogs"}}}',
        )


if __name__ == "__main__":
    main()
