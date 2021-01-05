import random
from functools import reduce
from math import floor
from string import ascii_uppercase
from typing import Dict, List, NamedTuple, Set, Tuple

from .api_types import Countries, Hex, Hexmap, Terrains

# generation code from https://welshpiper.com/hex-based-campaign-design-part-1/
class TerrainData(NamedTuple):
    primary: List[str]
    secondary: List[str]
    tertiary: List[str]
    wildcards: List[str]


TRANSITIONS = {
    "Water": TerrainData(primary=["Water"], secondary=["Plains"], tertiary=["Forest"], wildcards=["Swamp", "Desert", "Hills"]),
    "Swamp": TerrainData(primary=["Swamp"], secondary=["Plains"], tertiary=["Forest"], wildcards=["Water"]),
    "Desert": TerrainData(primary=["Desert"], secondary=["Hills"], tertiary=["Plains"], wildcards=["Water", "Mountains"]),
    "Plains": TerrainData(primary=["Plains"], secondary=["Forest"], tertiary=["Hills"], wildcards=["Water", "Swamp", "Desert"]),
    "Forest": TerrainData(primary=["Forest"], secondary=["Plains"], tertiary=["Hills"], wildcards=["Water", "Swamp", "Desert"]),
    "Hills": TerrainData(primary=["Hills"], secondary=["Mountains"], tertiary=["Plains"], wildcards=["Water", "Desert", "Forest"]),
    "Mountains": TerrainData(primary=["Mountains"], secondary=["Hills"], tertiary=["Forest"], wildcards=["Desert"]),
}

def generate(num_rows: int, num_columns: int, starting_terrain: Dict[Tuple[int, int], str]) -> List[Hex]:
    terrain = {k: v for k, v in starting_terrain.items()}
    if not terrain:
        terrain[(num_rows // 2, num_columns // 2)] = random.choice(list(TRANSITIONS))

    neighbors_map = _calc_neighbors(num_rows, num_columns)

    while True:
        terrain_neighbors = [(cur, ngh)
            for cur in terrain
            for ngh in neighbors_map[cur]
            if ngh not in terrain]
        if not terrain_neighbors:
            break
        from_hex, to_hex = random.choice(terrain_neighbors)
        terrain[to_hex] = _choose_terrain(TRANSITIONS[terrain[from_hex]])

    def make_hex(coord: Tuple[int, int]) -> Hex:
        row, column = coord
        rn = ascii_uppercase[row // 26] + ascii_uppercase[row % 26]
        nm = f"{rn}{column+1:02}"
        return Hex(
            name=nm,
            row=row,
            column=column,
            terrain=terrain[coord],
            country=random.choice(Countries),
        )

    return [
        make_hex(k) for k in terrain
    ]


def generate_from_mini(num_rows: int, num_columns: int, minimap: List[str]) -> List[Hex]:
    row_project = _calc_axis_projection(len(minimap), num_rows)
    col_project = _calc_axis_projection(len(minimap[0]), num_columns)

    mini_names = {
        "^": "Mountains",
        "n": "Hills",
        ".": "Plains",
        ":": "Desert",
        "\"": "Forest",
        "~": "Water",
        "&": "Swamp",
    }

    def project_choose(row, col) -> str:
        sym = minimap[row_project[row]][col_project[col]]
        return _choose_terrain(TRANSITIONS[mini_names[sym]])

    terrain = {
        (row, col): project_choose(row, col)
        for row in range(num_rows)
        for col in range(num_columns)
    }

    neighbors_map = _calc_neighbors(num_rows, num_columns)
    _adjust_terrain(terrain, neighbors_map)

    def make_hex(coord: Tuple[int, int]) -> Hex:
        row, column = coord
        rn = ascii_uppercase[row // 26] + ascii_uppercase[row % 26]
        nm = f"{rn}{column+1:02}"
        return Hex(
            name=nm,
            row=row,
            column=column,
            terrain=terrain[coord],
            country=random.choice(Countries),
        )

    return [
        make_hex(k) for k in terrain
    ]


def _calc_neighbors(num_rows: int, num_columns: int) -> Dict[Tuple[int, int], Set[Tuple[int, int]]]:
    ret = {}
    # per https://www.redblobgames.com/grids/hexagons/
    # but we flip row/col
    evenq_directions = [
        [[+1, +1], [0, +1], [-1, 0],
        [0, -1], [+1, -1], [+1, 0]],
        [[0, +1], [-1, +1], [-1, 0],
        [-1, -1], [0, -1], [+1, 0]],
    ]
    for row in range(0, num_rows):
        for col in range(0, num_columns):
            ret[(row, col)] = {(row + dir[0], col + dir[1])
                for dir in evenq_directions[col & 1]
                if (0 <= (row + dir[0]) < num_rows) and
                   (0 <= (col + dir[1]) < num_columns)}
    return ret


def _calc_axis_projection(small: int, big: int) -> Dict[int, int]:
    ratio = small / big
    return {idx: floor(ratio * idx) for idx in range(big)}


def _choose_terrain(data: TerrainData) -> str:
    xs = []
    if data.primary:
        for _ in range(12):
            xs.append(data.primary)
    if data.secondary:
        for _ in range(3):
            xs.append(data.secondary)
    if data.tertiary:
        for _ in range(2):
            xs.append(data.tertiary)
    if data.wildcards:
        for _ in range(1):
            xs.append(data.wildcards)
    return random.choice(random.choice(xs))


def _adjust_terrain(terrain: Dict[Tuple[int, int], str], neighbor_map: Dict[Tuple[int, int], Set[Tuple[int, int]]]) -> None:
    def _neighbor_count(coord: Tuple[int, int], ttype: str) -> int:
        return len([1 for ngh in neighbor_map[coord] if terrain[ngh] == ttype])

    near_water = {coord: cnt for coord, cnt in (
        (coord, _neighbor_count(coord, "Water"))
        for coord, ttype in terrain.items()
        if ttype != "Water"
    ) if cnt >= 1}

    def nm(coord):
        row, column = coord
        rn = ascii_uppercase[row // 26] + ascii_uppercase[row % 26]
        return f"{rn}{column+1:02}"

    for coord, cnt in near_water.items():
        # reduce the number of islands:
        if cnt >= 4 and random.randint(1, 100) < 60:
            terrain[coord] = "Water"
        elif cnt >= 2 and random.randint(1, 100) < 75:
            terrain[coord] = "Coastal"

    num_rows = max(x[0] for x in terrain) + 1

    hot_forests = [coord for coord, ttype in terrain.items() if ttype == "Forest" and coord[0] >= num_rows // 2]
    jungle_chance = {k: p * 10 for k, p in _calc_axis_projection(10, num_rows).items()}
    for coord in hot_forests:
        if random.randint(1, 100) < jungle_chance[coord[0]]:
            terrain[coord] = "Jungle"

    cold_lands = [coord for coord, ttype in terrain.items() if ttype not in ("Mountains", "Water") and coord[0] <= num_rows // 4]
    arctic_chance = {k: 80 - p * 15 for k, p in _calc_axis_projection(20, num_rows).items()}
    for coord in cold_lands:
        if random.randint(1, 100) < arctic_chance[coord[0]]:
            terrain[coord] = "Arctic"

    num_cities = 25
    clear_radius = 3
    city_spots = {coord for coord, ttype in terrain.items() if ttype != "Water"}
    for _ in range(num_cities):
        print("Placing city ....")
        if not city_spots:
            print("No more spots!")
        coord = random.choice(list(city_spots))
        terrain[coord] = "City"
        clear_set = {coord}
        for _cr in range(clear_radius):
            clear_set = reduce(lambda tot, e: tot | neighbor_map[e], clear_set, set())
        city_spots -= clear_set
