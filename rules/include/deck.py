import random
from typing import List, Sequence, TypeVar


T = TypeVar("T")


def shuffle_discard(cards: Sequence[T]) -> List[T]:
    ret = list(cards)
    random.shuffle(ret)
    for _ in range((len(ret) // 10) + 1):
        ret.pop()
    return ret
