import random
from enum import Enum

from colors import colors
from common import Card, Deck, flatten
from skills import *

class Terrain:
    def __init__(self, name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck):
        self.name = name
        self.symbol = symbol
        self.fmt = fmt
        self.bg_fmt = bg_fmt
        self.base_difficulty = base_difficulty
        self.base_skills = base_skills
        self.move_distances = move_distances
        self.deck = deck

class MountainTerrain(Terrain):
    def __init__(self, name, symbol, base_difficulty):
        fmt = colors.fg.darkgrey
        bg_fmt = colors.bg.darkgrey
        base_skills = { MOUNTAIN_LORE, MOUNTAIN_LORE, CLIMB }
        move_distances = [0, 0, 1, 1, 1, 2]
        deck = Deck(flatten(
            (Card("Chasm", {ACROBATICS, THROW, NAVIGATION}), 2),
            (Card("Avalanche", {MIGHT, SPEED, ACROBATICS}), 2),
            (Card("Mountain Shrine", {SPIRIT_BINDING, RESEARCH, MECHANISMS}), 2),
            (Card("Creatures of the Mountain", {DEBATE, PICKPOCKET, MIGHT}), 2),
            (Card("Dark Cave", {ARCHITECTURE, NAVIGATION, THAUMATURGY}), 2),
            (Card("Icy Wind", {ENDURANCE, ACROBATICS, MESMERISM}), 2),
        ))
        super().__init__(name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck)

class DesertTerrain(Terrain):
    def __init__(self, name, symbol, base_difficulty):
        fmt = colors.fg.yellow
        bg_fmt = colors.bg.orange
        base_skills = { DESERT_LORE, DESERT_LORE, ENDURANCE }
        move_distances = [0, 1, 1, 1, 2, 3]
        deck = Deck(flatten(
            (Card("Oasis", {CAROUSING, OBSERVATION, DOCTOR}), 2),
            (Card("Sandstorm", {NAVIGATION, ENDURANCE, MIGHT}), 2),
            (Card("Desert Beast", {CHARM, STEALTH, ANIMAL_TRAINING}), 2),
            (Card("Extreme Heat", {ENDURANCE, ENDURANCE, DESERT_LORE}), 2),
            (Card("Strange Constellations", {SPIRIT_BINDING, NAVIGATION, MESMERISM}), 2),
            (Card("Mirage", {OBSERVATION, ARCHITECTURE, MESMERISM}), 2),
        ))
        super().__init__(name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck)

class WaterTerrain(Terrain):
    def __init__(self, name, symbol, fmt, bg_fmt, base_difficulty):
        base_skills = { SEA_LORE, SEA_LORE, NAVIGATION }
        move_distances = [1, 1, 2, 2, 3, 3]
        deck = Deck(flatten(
            (Card("Storm", {}), 2),
            (Card("Dangerous Rocks", {}), 2),
            (Card("Whirlpool", {}), 2),
            (Card("Aquatic Beast", {}), 2),
            (Card("Ghost Ship", {}), 2),
            (Card("Becalmed", {}), 2),
        ))
        super().__init__(name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck)

class GrasslandsTerrain(Terrain):
    def __init__(self):
        name = "Grasslands"
        symbol = "g"
        fmt = colors.fg.green
        bg_fmt = colors.bg.green
        base_difficulty = 1
        base_skills = { PLAINS_LORE, PLAINS_LORE, RIDE }
        move_distances = [1, 1, 2, 2, 3, 3]
        deck = Deck(flatten(
            (Card("Circling Birds", {}), 2),
            (Card("Strange Vegetation", {}), 2),
            (Card("Distant Riders", {}), 2),
            (Card("Sudden Storm", {}), 2),
            (Card("Beasts of the Grasslands", {}), 2),
            (Card("Dangerous Footing", {}), 2),
        ))
        super().__init__(name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck)

class CityTerrain(Terrain):
    def __init__(self):
        name = "City"
        symbol = "C"
        fmt = colors.fg.magenta
        bg_fmt = colors.bg.magenta
        base_difficulty = 2
        base_skills = { OBSERVATION, ARCHITECTURE, CAROUSING }
        move_distances = [0, 0, 0, 1, 1, 1]
        deck = Deck(flatten(
            (Card("Street Market", {OBSERVATION, APPRAISAL, PICKPOCKET}), 2),
            (Card("Wandering Prophet", {}), 2),
            (Card("Tavern Brawl", {}), 2),
            (Card("Statuary Garden", {}), 2),
            (Card("???", {}), 2),
            (Card("???", {}), 2),
        ))
        super().__init__(name, symbol, fmt, bg_fmt, base_difficulty, base_skills, move_distances, deck)

TERRAINS = [
    MountainTerrain("Low Mountains", "m", 2),
    MountainTerrain("High Mountains", "M", 4),
    DesertTerrain("Light Desert", "d", 2),
    DesertTerrain("Deep Desert", "D", 3),
    WaterTerrain("Shallow Water", "~", colors.fg.cyan, colors.bg.cyan, 2),
    WaterTerrain("Deep Water", "~", colors.fg.blue, colors.bg.blue, 3),
    GrasslandsTerrain(),
    CityTerrain(),
]

class Hex:
    def __init__(self, name, terrain):
        self.name = name
        self.terrain = terrain
        self.card_difficulty = terrain.base_difficulty
        self.card_skills = terrain.base_skills
        self.move_distances = terrain.move_distances
        self.neighbors = []
        self.dirs = {}
        self.features = {}

    def render(self, selected):
        reg_fmt = self.terrain.fmt
        inv_fmt = colors.fg.black + self.terrain.bg_fmt
        if self.features:
            sym = list(self.features.values())[0].symbol
            return inv_fmt + sym + colors.reset
        elif selected:
            return inv_fmt + self.terrain.symbol + colors.reset
        else:
            return reg_fmt + self.terrain.symbol + colors.reset

    def draw(self):
        return self.terrain.deck.draw()

    def get_move_distance(self):
        return random.choice(self.move_distances)

class Feature:
    def __init__(self, name, symbol):
        self.name = name
        self.symbol = symbol
        self.hex = None

class Hexmap:
    def __init__(self, data):
        self._set_hexes(data)
        self._features = {}

    def display(self, messages, selected_hexes):
        for y in range(self.height):
            for x in range(self.width):
                hn = "{},{}".format(x+1, y+1)
                h = self._hexes[hn]
                print(h.render(hn in selected_hexes), end="")
            if messages:
                print("        " + messages.pop(0))
            else:
                print()

    def get_hex(self, hex_name):
        return self._hexes[hex_name]

    def add_feature(self, feature, hex_name):
        feature.hex = self._hexes[hex_name]
        feature.hex.features[feature.name] = feature
        self._features[feature.name] = feature

    def find_feature(self, feature_name):
        feature = self._features[feature_name]
        return feature.hex

    def move_feature(self, feature_name, hex_name):
        feature = self._features[feature_name]
        del feature.hex.features[feature_name]
        feature.hex = self._hexes[hex_name]
        feature.hex.features[feature.name] = feature

    def random_path(self, feature_name, amt):
        feature = self._features[feature_name]
        cc = feature.hex
        excluded = {cc.name}
        for _ in range(amt):
            neighbors = {n.name for n in cc.neighbors} - excluded
            if not neighbors:
                break
            cc = self._hexes[random.choice(list(neighbors))]
            print("Moved to {} - {}".format(cc.name, cc.terrain.name))
            excluded |= neighbors
        return cc

    def vi_path(self, feature_name, dirs):
        feature = self._features[feature_name]
        cc = feature.hex
        for d in dirs:
            if d == ".":
                continue
            if d not in cc.dirs:
                print("Bonk!")
            else:
                cc = cc.dirs[d]
        return cc

    def random_move(self, feature_name, amt):
        target_hex = self.random_path(feature_name, amt)
        self.move_feature(feature_name, target_hex.name)

    def vi_move(self, feature_name, dirs):
        target_hex = self.vi_path(feature_name, dirs)
        self.move_feature(feature_name, target_hex.name)

    def _set_hexes(self, data):
        self.width = len(data[0])
        self.height = len(data)
        tmap = {t.symbol: t for t in TERRAINS}
        self._hexes = {}
        for y, row in enumerate(data):
            for x, c in enumerate(row):
                terrain = tmap[c]
                name = "{},{}".format(x+1, y+1)
                h = Hex(name, terrain)
                self._hexes[name] = h
                hn = []
                if y > 0:
                    n = self._hexes["{},{}".format(x+1, y)]
                    h.dirs["k"] = n
                    n.dirs["j"] = h
                    hn.append(n)
                if x > 0:
                    n = self._hexes["{},{}".format(x, y+1)]
                    h.dirs["h"] = n
                    n.dirs["l"] = h
                    hn.append(n)
                if y > 0 and x > 0:
                    n = self._hexes["{},{}".format(x, y)]
                    h.dirs["y"] = n
                    n.dirs["n"] = h
                    hn.append(n)
                if y > 0 and x < len(row) - 1:
                    n = self._hexes["{},{}".format(x+2, y)]
                    h.dirs["u"] = n
                    n.dirs["b"] = h
                for n in hn:
                    n.neighbors.append(h)
                    h.neighbors.append(n)

if __name__ == "__main__":
    MAP_DATA = (
        "MMmmDDD",
        "MMmdDDD",
        "MmdddDD",
        "mdddDDD",
        "ddddDDD",
        "ggCdddD",
        "~~ggddd",
    )
    m = Hexmap(MAP_DATA)
    m.add_feature(Feature("Bob", "@"), "4,4")
    m.add_feature(Feature("Bob2", "@"), "1,1")
    m.add_feature(Feature("Bob3", "@"), "3,1")
    m.add_feature(Feature("Bob4", "@"), "1,6")
    m.add_feature(Feature("Bob5", "@"), "2,7")
    m.add_feature(Feature("Bob4", "@"), "3,6")
    m.display([])
    m.random_move("Bob", 2)
    m.display([])
