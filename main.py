#!/usr/bin/python3
import random
import re
from argparse import ArgumentParser, Namespace

from character import Character
from metadeck import MetaDeck
from hexmap import Feature, Hexmap
from job import Job

def fill_messages(messages, pc):
    while len(messages) < 7:
        messages.append("")
    messages[0] = "Turns: {:02d}    Health: {:d}     Reputation: {:d}/{:d}".format(
        pc.turns, pc.health, pc.reputation, pc.max_reputation
    )
    messages[1] = "Coins: {:d}     Resources: {:d}   Tools: {:d}".format(
        pc.coins, pc.resources, len(pc.tools),
    )
    messages[2] = ""

    skill_ranks = list(sorted((it for it in pc.skills.items() if it[1] > 0), key=lambda o: o[0]))
    idx = 3
    while skill_ranks:
        line = "   ".join(f"{sr[0]}: {sr[1]}" for sr in skill_ranks[0:3])
        messages[idx] = line
        idx += 1
        skill_ranks = skill_ranks[3:]

def do_travel(pc, hexmap, deck, dirs):
    hexmap.vi_move(pc.name, dirs)
    card = deck.draw_hex(pc, hexmap)
    card.resolve(pc, hexmap)

def do_camp(pc, hexmap, deck) -> None:
    print("Campin' or glampin'?")

def main(args: Namespace) -> None:
    deck = MetaDeck()
    MAP_DATA = (
        "MMmmDDD",
        "MMmdDDD",
        "MmdddDD",
        "mdddDDD",
        "ddddDDD",
        "ggCdddD",
        "~~ggddd",
    )
    pc = Character("PC", Job())
    m = Hexmap(MAP_DATA)
    m.add_feature(Feature(pc.name, "@"), "4,4")

    if args.skill > 0:
        bumps = random.sample(pc.job.learn_skills, 4)
        for idx, sk in enumerate(bumps):
            val = args.skill if idx < 2 else (args.skill - 1)
            pc.skills[sk] = val

    # fill initial tableau
    tableau = []
    for _ in range(0, 3):
        card = deck.draw_job(pc, m)
        tableau.append(card)

    idx = 0
    while pc.turns > 0:
        messages = []
        fill_messages(messages, pc)
        m.display(messages, {c.target_hex for c in tableau if c.target_hex})
        print(f"Turn {idx+1}")
        for idx, card in enumerate(tableau):
            print(f"{'abcde'[idx]}. {card.preview(pc)}")
        print("t. Travel (ykuh.lbjn)")
        print("x. Camp")
        print("Your choice: ", end="")
        line = input().lower()
        if not line:
            continue
        if line[0] in "abcde":
            c_idx = "abcde".index(line[0])
            card = tableau.pop(c_idx)
            card.resolve(pc, m)
            tableau.append(deck.draw_job(pc, m))
        elif line[0] == "t":
            ww = re.split(r"\s+", line, 2)
            dirs = None if len(ww) == 1 else ww[1]
            if not dirs or any(d not in "ykuh.lbjn" for d in dirs):
                print("move <dirs> - ykuh.lbjn")
                print()
                continue
            if len(dirs) > 3:
                print("max 3 steps")
                print()
                continue
            do_travel(pc, m, deck, dirs)
        elif line[0] == "c":
            do_camp(pc, m, deck)
        else:
            print("???")
            print()
            continue
        pc.end_turn()
        for card in tableau:
            card.duration -= 1
        tableau = [c for c in tableau if c.duration > 0]
        while len(tableau) < 3:
            tableau.append(deck.draw_job(pc, m))
        idx += 1


def parse_args() -> Namespace:
    parser = ArgumentParser(description='Run game')
    parser.add_argument('--skill', type=int, default=0, help='starting skills')
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
