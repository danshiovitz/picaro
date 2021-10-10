from typing import Any, Callable, List, Optional, TypeVar


def clamp(val: int, min: Optional[int] = None, max: Optional[int] = None) -> int:
    if min is not None and val < min:
        return min
    elif max is not None and val > max:
        return max
    else:
        return val


def with_s(val: int, word: str, word_s: Optional[str] = None) -> str:
    if val == 1 or val == -1:
        return f"{val:+} {word}"
    elif word_s is None:
        return f"{val:+} {word}s"
    else:
        return f"{val:+} {word_s}"


T = TypeVar("T")


def pop_func(lst: List[T], func: Callable[[T], bool]) -> T:
    for i in range(len(lst)):
        if func(lst[i]):
            val = lst.pop(i)
            return val
    raise IndexError("No matching value for pop_func")
