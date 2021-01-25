from pathlib import Path
from typing import Type, TypeVar

from picaro.common.serializer import deserialize


T = TypeVar("T")
def load_json(filename: str, cls: Type[T]) -> T:
    with open(Path(__file__).absolute().parent / "data" / f"{filename}.json") as f:
        return deserialize(f.read(), cls)
