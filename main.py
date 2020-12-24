#!/usr/bin/python3
import random
import re

from character import Character
from metadeck import MetaDeck
from hexmap import Feature, Hexmap
from job import Job

def fill_messages(messages, pc):
    while len(messages) < 7:
        messages.append("")
    messages[1] = "Turns: {:02d}    Danger: {:d}    Reputation: {:d}/{:d}".format(
        pc.turns, pc.danger, pc.reputation, pc.max_reputation
    )
    messages[2] = "Coins: {:d}    Resources: {:d}    Tools: {:d}".format(
        pc.coins, pc.resources, len(pc.tools),
    )
    sv = (str(s[1]) for s in sorted(pc.skills.items(), key=lambda o: o[0]))
    messages[3] = "".join(sv)
    
def do_job(pc, hexmap, deck):
    distance = pc.job.get_move_distance()
    if distance:
        hexmap.random_move(pc.name, distance)
    cur_hex = hexmap.find_feature(pc.name)
    card = deck.draw_job(pc, cur_hex)
    card.display(pc)
    card.resolve(pc, hexmap)

def do_travel(pc, hexmap, deck, dirs):
    hexmap.vi_move(pc.name, dirs)
    cur_hex = hexmap.find_feature(pc.name)
    card = deck.draw_hex(pc, cur_hex)
    card.display(pc)
    card.resolve(pc, hexmap)

def do_camp(pc, hexmap, deck):
    print("Campin' or glampin'?")
    
def main():
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
    idx = 0
    while pc.turns > 0:
        messages = []
        fill_messages(messages, pc)
        m.display(messages)
        print("{}. Job, travel, camp? ".format(idx+1), end="")
        line = input().lower()
        if not line:
            continue
        if line[0] == "j":
            do_job(pc, m, deck)
        elif line[0] == "t":
            ww = re.split(r'\s+', line, 2)
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
        idx += 1

if __name__ == "__main__":
    main()
