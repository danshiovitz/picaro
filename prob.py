#!/usr/bin/python3
import random
from collections import defaultdict


orig_deck = list(["A", "B", "C", "D"] * 25);
deck = []

def draw_one():
    global deck, orig_deck
    if not deck:
        deck = orig_deck[:]
        random.shuffle(deck)
    return deck.pop(0)

def draw_until(v):
    while True:
        c = draw_one()
        if c == v:
            return

def draw_all():
    cnts = defaultdict(int)
    for i in range(1000000):
        if i % 20 == 0:
            for _ in range(4):
                draw_until("A")
        c = draw_one()
        cnts[c] += 1
    print(cnts)

if __name__ == "__main__":
    draw_all()
    
        
