import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).absolute().parent.parent.parent.parent))

from typing import List

from picaro.rules.lib.deck import shuffle_discard
from picaro.rules.types.internal import TravelCard, TravelCardType


def next_card(nothing_count: int) -> TravelCard:
    def _make_deck() -> List[TravelCard]:
        cards = []
        cards.extend([TravelCard(type=TravelCardType.NOTHING, value=0)] * nothing_count)
        for i in range(1, 6):
            cards.extend([TravelCard(type=TravelCardType.DANGER, value=i)] * 3)
        for _ in range(2):
            cards.append(TravelCard(type=TravelCardType.SPECIAL, value=None))
        return shuffle_discard(cards)

    cards = []
    while True:
        if not cards:
            cards = _make_deck()
        yield cards.pop(0)


def next_roll(nothing_count: int) -> TravelCard:
    cards = []
    cards.extend([TravelCard(type=TravelCardType.DANGER, value=1)] * 8)
    for i in range(2, 6):
        cards.extend([TravelCard(type=TravelCardType.DANGER, value=i)] * 5)
    for _ in range(2):
        cards.append(TravelCard(type=TravelCardType.SPECIAL, value=0))
    while len(cards) < 100:
        cards.append(TravelCard(type=TravelCardType.NOTHING, value=0))
    while True:
        yield random.choice(cards)


def run() -> None:
    turns = 10000
    draws_per_turn = 3
    nothing_count = 14
    dangers = list(range(1, 6))

    # deck = next_card(nothing_count)
    deck = next_roll(nothing_count)
    all_draws = [next(deck) for _ in range(turns * draws_per_turn)]
    dr_results = []
    for danger in dangers:
        special_cnt = 0
        encounter_cnt = 0
        idx = 0
        for _ in range(turns):
            for _ in range(draws_per_turn):
                draw = all_draws[idx]
                idx += 1
                if draw.type == TravelCardType.SPECIAL:
                    special_cnt += 1
                    break
                elif draw.type == TravelCardType.DANGER and draw.value <= danger:
                    encounter_cnt += 1
                    break
        dr_results.append((special_cnt * 100 / turns, encounter_cnt * 100 / turns))
    line = f"Nothings: {nothing_count}"
    for danger in dangers:
        line += f"; @{danger} {dr_results[danger-1][0]:.1f}%, {dr_results[danger-1][1]:.1f}%"
    print(line)


if __name__ == "__main__":
    run()
