import random
from collections import defaultdict
from dataclasses import dataclass
from functools import reduce
from math import floor
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple, Type, TypeVar

from picaro.common.hexmap.types import CubeCoordinate, OffsetCoordinate
from picaro.common.hexmap.utils import calc_offset_neighbor_map
from picaro.common.serializer import deserialize
from picaro.server.api_types import (
    Action,
    Choice,
    Choices,
    Country,
    CreateGameRequest,
    Effect,
    EffectType,
    EntityType,
    Entity,
    Filter,
    FilterType,
    Gadget,
    Hex,
    Job,
    ProjectType,
    TemplateCard,
    TemplateCardType,
    TemplateDeck,
    Token,
)


def generate_game_v2(name: str, json_dir: Path) -> CreateGameRequest:
    skills = _load_json(json_dir, "skills", str)
    resources = Resources
    jobs = _load_json(json_dir, "jobs", Job)
    template_decks = _load_json(json_dir, "decks", TemplateDeck)
    # project_types = _load_json(json_dir, "project_types", ProjectType)
    zodiacs = _load_json(json_dir, "zodiacs", str)
    hexes, countries, entities = generate_map_v2()
    return CreateGameRequest(
        name=name,
        skills=skills,
        resources=resources,
        jobs=jobs,
        template_decks=template_decks,
        # project_types=project_types,
        zodiacs=zodiacs,
        hexes=hexes,
        countries=countries,
        entities=entities,
    )


T = TypeVar("T")


def _load_json(json_dir: Path, fname: str, type: Type[T]) -> List[T]:
    json_dir_path = json_dir / fname
    if json_dir_path.is_dir():
        ret = []
        for fname in json_dir_path.glob("**/*"):
            if fname.is_file():
                with open(fname) as f:
                    ret.append(deserialize(f.read(), type))
        return ret
    else:
        with open(json_dir / (fname + ".json")) as f:
            return deserialize(f.read(), List[type])


# generation code from https://welshpiper.com/hex-based-campaign-design-part-1/
@dataclass(frozen=True)
class TerrainData:
    primary: List[str]
    secondary: List[str]
    tertiary: List[str]
    wildcards: List[str]


TRANSITIONS = {
    "Water": TerrainData(
        primary=["Water"],
        secondary=["Plains"],
        tertiary=["Forest"],
        wildcards=["Swamp", "Desert", "Hills"],
    ),
    "Swamp": TerrainData(
        primary=["Swamp"],
        secondary=["Plains"],
        tertiary=["Forest"],
        wildcards=["Water"],
    ),
    "Desert": TerrainData(
        primary=["Desert"],
        secondary=["Hills"],
        tertiary=["Plains"],
        wildcards=["Water", "Mountains"],
    ),
    "Plains": TerrainData(
        primary=["Plains"],
        secondary=["Forest"],
        tertiary=["Hills"],
        wildcards=["Water", "Swamp", "Desert"],
    ),
    "Forest": TerrainData(
        primary=["Forest"],
        secondary=["Plains"],
        tertiary=["Hills"],
        wildcards=["Water", "Swamp", "Desert"],
    ),
    "Hills": TerrainData(
        primary=["Hills"],
        secondary=["Mountains"],
        tertiary=["Plains"],
        wildcards=["Water", "Desert", "Forest"],
    ),
    "Mountains": TerrainData(
        primary=["Mountains"],
        secondary=["Hills"],
        tertiary=["Forest"],
        wildcards=["Desert"],
    ),
}


Countries = [
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Theta",
    "Iota",
]


Resources = [
    "Steel",
    "Silks",
    "Jewels",
    "Glass",
    "Timber",
    "Herbs",
    "Stone",
    "Wine",
]


def generate(
    num_rows: int, num_columns: int, starting_terrain: Dict[OffsetCoordinate, str]
) -> List[Hex]:
    terrain = {k: v for k, v in starting_terrain.items()}
    if not terrain:
        terrain[
            OffsetCoordinate(row=num_rows // 2, column=num_columns // 2)
        ] = random.choice(list(TRANSITIONS))

    neighbors_map = calc_offset_neighbor_map(num_rows, num_columns)

    while True:
        terrain_neighbors = [
            (cur, ngh)
            for cur in terrain
            for ngh in neighbors_map[cur]
            if ngh not in terrain
        ]
        if not terrain_neighbors:
            break
        from_hex, to_hex = random.choice(terrain_neighbors)
        terrain[to_hex] = _choose_terrain(TRANSITIONS[terrain[from_hex]])

    def make_hex(coord: OffsetCoordinate) -> Hex:
        row, column = (coord.row, coord.column)
        return Hex(
            name=coord.get_name(),
            coordinate=coord,
            terrain=terrain[coord],
            country=random.choice(Countries),
            danger=1,
        )

    return [make_hex(k) for k in terrain]


def generate_map_v2() -> Tuple[List[Hex], List[Country], List[Entity]]:
    minimap = [
        "^n::n::~",
        'n:n."..~',
        '"."."".~',
        '^n."".nn',
        "^.~~~~~~",
        '.."~~..:',
        '""""^::n',
        '&&"^n:::',
    ]
    hexes, countries, mine_locs = generate_from_mini(50, 50, minimap)

    # using http://www.dungeoneering.net/d100-list-fantasy-town-names/ as a placeholder
    # for now
    city_names = [
        "Aerilon",
        "Aquarin",
        "Aramoor",
        "Azmar",
        "Beggar's Hole",
        "Black Hollow",
        "Blue Field",
        "Briar Glen",
        "Brickelwhyte",
        "Broken Shield",
        "Boatwright",
        "Bullmar",
        "Carran",
        "City of Fire",
        "Coalfell",
        "Cullfield",
        "Darkwell",
        "Deathfall",
        "Doonatel",
        "Dry Gulch",
        "Easthaven",
        "Ecrin",
        "Erast",
        "Far Water",
        "Firebend",
        "Fool's March",
        "Frostford",
        "Goldcrest",
        "Goldenleaf",
        "Greenflower",
        "Garen's Well",
        "Haran",
        "Hillfar",
        "Hogsfeet",
        "Hollyhead",
        "Hull",
        "Hwen",
        "Icemeet",
        "Ironforge",
        "Irragin",
    ]
    random.shuffle(city_names)

    mine_set = {m for m in mine_locs}
    mine_rs = {c.name: c.resources[0] for c in countries}

    entities = []

    for hx in hexes:
        if hx.terrain == "City":
            actions = [
                Action(
                    name="Trade",
                    benefit=[
                        Effect(
                            type=EffectType.QUEUE_ENCOUNTER,
                            value=TemplateCard(
                                copies=1,
                                name="Trade",
                                desc="...",
                                type=TemplateCardType.SPECIAL,
                                data="trade",
                            ),
                        ),
                    ],
                    cost=[],
                    uuid="",
                    is_private=False,
                    filters=[
                        Filter(type=FilterType.NEAR_HEX, subtype=hx.name, value=0),
                    ],
                    route=[],
                ),
            ]
            city_name = city_names.pop(0)
            entity = Entity(
                type=EntityType.LANDMARK,
                subtype="city",
                name=city_name,
                gadgets=[
                    Gadget(
                        uuid="",
                        name=city_name,
                        overlays=[],
                        triggers=[],
                        actions=actions,
                        entity=None,
                    ),
                ],
                locations=[hx.name],
                uuid="",
            )
            entities.append(entity)

        if hx.name in mine_set:
            actions = [
                Action(
                    name=f"Gather {mine_rs[hx.country]}",
                    cost=(Effect(type=EffectType.MODIFY_ACTIVITY, value=-1),),
                    benefit=(
                        Effect(
                            type=EffectType.MODIFY_RESOURCES,
                            subtype=mine_rs[hx.country],
                            value=1,
                        ),
                    ),
                    is_private=False,
                    filters=[
                        Filter(type=FilterType.NEAR_HEX, subtype=hx.name, value=0),
                    ],
                    uuid="",
                    route=[],
                ),
            ]
            mine_name = f"{mine_rs[hx.country]} Source"
            entity = Entity(
                type=EntityType.LANDMARK,
                subtype="mine",
                name=mine_name,
                gadgets=[
                    Gadget(
                        uuid="",
                        name=mine_name,
                        overlays=[],
                        triggers=[],
                        actions=actions,
                        entity=None,
                    ),
                ],
                locations=[hx.name],
                uuid="",
            )
            entities.append(entity)

    return hexes, countries, entities


def generate_from_mini(
    num_rows: int, num_columns: int, minimap: List[str]
) -> Tuple[List[Hex], List[Country], List[str]]:
    row_project = _calc_axis_projection(len(minimap), num_rows)
    col_project = _calc_axis_projection(len(minimap[0]), num_columns)

    mini_names = {
        "^": "Mountains",
        "n": "Hills",
        ".": "Plains",
        ":": "Desert",
        '"': "Forest",
        "~": "Water",
        "&": "Swamp",
    }

    def project_choose(row: int, col: int) -> str:
        sym = minimap[row_project[row]][col_project[col]]
        return _choose_terrain(TRANSITIONS[mini_names[sym]])

    terrain = {
        OffsetCoordinate(row=row, column=col): project_choose(row, col)
        for row in range(num_rows)
        for col in range(num_columns)
    }

    neighbors_map = calc_offset_neighbor_map(num_rows, num_columns)
    _adjust_terrain(terrain, neighbors_map)
    country_map, capitol_coords = _make_country_map(terrain, neighbors_map)
    cap_set = {c for c in capitol_coords}
    country_data = {}

    def make_hex(coord: OffsetCoordinate) -> Hex:
        row, column = (coord.row, coord.column)
        if coord in cap_set:
            country_data[country_map[coord]] = coord.get_name()
        return Hex(
            name=coord.get_name(),
            coordinate=coord,
            terrain=terrain[coord],
            country=country_map[coord],
            danger=2,
        )

    hexes = [make_hex(k) for k in terrain]
    rs = Resources[:]
    random.shuffle(rs)
    countries = [
        Country(
            uuid="",
            name=c,
            capitol_hex=country_data[c],
            resources=[rs.pop(0), random.choice(Resources)],
        )
        for c in country_data.keys()
    ]

    mines = []
    for ctry in countries:
        hxs = [
            hx
            for hx in hexes
            if hx.country == ctry.name and terrain[hx.coordinate] != "City"
        ]
        mines.append(random.choice(hxs).name)

    return hexes, countries, mines


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


def _adjust_terrain(
    terrain: Dict[OffsetCoordinate, str],
    neighbor_map: Dict[OffsetCoordinate, Set[OffsetCoordinate]],
) -> None:
    def _neighbor_count(coord: OffsetCoordinate, ttype: str) -> int:
        return len([1 for ngh in neighbor_map[coord] if terrain[ngh] == ttype])

    near_water = {
        coord: cnt
        for coord, cnt in (
            (coord, _neighbor_count(coord, "Water"))
            for coord, ttype in terrain.items()
            if ttype != "Water"
        )
        if cnt >= 1
    }

    for coord, cnt in near_water.items():
        # reduce the number of islands:
        if cnt >= 4 and random.randint(1, 100) < 80:
            terrain[coord] = "Water"
        elif cnt >= 2 and random.randint(1, 100) < 75:
            terrain[coord] = "Coastal"

    num_rows = max(x.row for x in terrain) + 1

    hot_forests = [
        coord
        for coord, ttype in terrain.items()
        if ttype == "Forest" and coord.row >= num_rows // 2
    ]
    jungle_chance = {k: p * 10 for k, p in _calc_axis_projection(10, num_rows).items()}
    for coord in hot_forests:
        if random.randint(1, 100) < jungle_chance[coord.row]:
            terrain[coord] = "Jungle"

    cold_lands = [
        coord
        for coord, ttype in terrain.items()
        if ttype not in ("Mountains", "Water") and coord.row <= num_rows // 4
    ]
    arctic_chance = {
        k: 80 - p * 15 for k, p in _calc_axis_projection(20, num_rows).items()
    }
    for coord in cold_lands:
        if random.randint(1, 100) < arctic_chance[coord.row]:
            terrain[coord] = "Arctic"

    num_cities = 25
    clear_radius = 3
    city_spots = {coord for coord, ttype in terrain.items() if ttype != "Water"}
    for _ in range(num_cities):
        if not city_spots:
            print("No more city spots!")
        coord = random.choice(list(city_spots))
        terrain[coord] = "City"
        clear_set = {coord}
        for _cr in range(clear_radius):
            clear_set = reduce(lambda tot, e: tot | neighbor_map[e], clear_set, set())
        city_spots -= clear_set


def _make_country_map(
    terrain_map: Dict[OffsetCoordinate, str],
    neighbors_map: Dict[OffsetCoordinate, Set[OffsetCoordinate]],
) -> Tuple[Dict[OffsetCoordinate, str], List[OffsetCoordinate]]:
    ret = {c: "Unassigned" for c in terrain_map}

    # first identify all wild areas
    wilds = _find_area("Water", terrain_map, neighbors_map) | _find_area(
        "Mountains", terrain_map, neighbors_map
    )
    for w in wilds:
        ret[w] = "Wild"

    best_score = -9999
    best_assignment = None
    best_capitols = None

    for _ in range(10):
        unassigned = {c for c, n in ret.items() if n == "Unassigned"}
        countries = Countries[:]
        random.shuffle(countries)
        capitols = dict(
            zip(_pick_capitols(unassigned, terrain_map, len(countries)), countries)
        )

        assignment = _assign_countries(unassigned, capitols, neighbors_map)
        score = _score_assignment(assignment)
        if best_assignment is None or score > best_score:
            best_score = score
            best_assignment = assignment
            best_capitols = list(capitols.keys())

    assert best_assignment is not None
    for c, n in best_assignment.items():
        ret[c] = n

    for c in ret:
        if ret[c] == "Unassigned":
            ret[c] = "Wild"

    return ret, best_capitols


def _find_area(
    area_type: str,
    terrain_map: Dict[OffsetCoordinate, str],
    neighbors_map: Dict[OffsetCoordinate, Set[OffsetCoordinate]],
) -> Set[OffsetCoordinate]:
    def type_neighbor_count(coord: OffsetCoordinate) -> int:
        return len([1 for ngh in neighbors_map[coord] if terrain_map[ngh] == area_type])

    area_set = {
        coord
        for coord, ttype in terrain_map.items()
        if ttype == area_type and type_neighbor_count(coord) >= 4
    }

    def non_area_neighbor_count(coord: OffsetCoordinate) -> int:
        return len([1 for ngh in neighbors_map[coord] if ngh not in area_set])

    while True:
        new_vals = set()
        for c in area_set:
            for ngh in neighbors_map[c]:
                if ngh in area_set:
                    continue
                # we go based on non_area_neighbor rather than area_neighbor count
                # to deal with being at the edge of the board
                if (
                    terrain_map[ngh] == area_type and non_area_neighbor_count(ngh) <= 3
                ) or (non_area_neighbor_count(ngh) <= 1):
                    new_vals.add(ngh)
        if not new_vals:
            break
        area_set |= new_vals
    return area_set


def _find_contiguous(
    unassigned: Set[OffsetCoordinate],
    neighbors_map: Dict[OffsetCoordinate, Set[OffsetCoordinate]],
) -> List[Set[OffsetCoordinate]]:
    ret = []
    cpy = unassigned.copy()
    while cpy:
        cc = next(iter(cpy))
        cpy.remove(cc)
        cur = {cc}
        while True:
            new_vals = set()
            for c in cur:
                for ngh in neighbors_map[c]:
                    if ngh not in cpy:
                        continue
                    new_vals.add(ngh)
                    cpy.remove(ngh)
            if not new_vals:
                break
            cur |= new_vals
        ret.append(cur)
    return ret


def _pick_capitols(
    unassigned: Set[OffsetCoordinate],
    terrain_map: Dict[OffsetCoordinate, str],
    cnt: int,
) -> List[OffsetCoordinate]:
    # pick relatively-separated cities to be the centers of the countries
    all_cities = sorted(
        [
            CubeCoordinate.from_row_col(c.row, c.column)
            for c, t in terrain_map.items()
            if t == "City" and c in unassigned
        ],
        key=lambda c: (c.to_offset().row, c.to_offset().column),
    )
    cities = [random.choice(all_cities)]
    all_cities.remove(cities[0])
    while len(cities) < cnt:
        max_min: Callable[[CubeCoordinate], int] = lambda c: min(
            c.distance(n) for n in cities
        )
        all_cities.sort(key=lambda c: (-max_min(c), c.x, c.y, c.z))
        cities.append(all_cities.pop(0))
    return [c.to_offset() for c in cities]


def _assign_countries(
    coords: Set[OffsetCoordinate],
    capitols: Dict[OffsetCoordinate, str],
    neighbors_map: Dict[OffsetCoordinate, Set[OffsetCoordinate]],
) -> Dict[OffsetCoordinate, str]:
    ret = {coord: country for coord, country in capitols.items()}
    countries: Dict[str, Set[OffsetCoordinate]] = {
        country: set() for country in capitols.values()
    }
    neighbors: Dict[str, Set[OffsetCoordinate]] = {
        country: set() for country in capitols.values()
    }

    def add_coord(country: str, coord: OffsetCoordinate) -> None:
        ret[coord] = country
        countries[country].add(coord)
        for nghs in neighbors.values():
            nghs.discard(coord)
        for ngh in neighbors_map[coord]:
            if ngh in coords and ngh not in ret:
                neighbors[country].add(ngh)

    for coord, country in capitols.items():
        add_coord(country, coord)

    did_any = True
    while did_any:
        did_any = False
        for country in countries:
            nghs = list(neighbors[country])
            if nghs:
                ngh = random.choice(nghs)
                add_coord(country, ngh)
                did_any = True
    return ret


def _score_assignment(
    assignment: Dict[OffsetCoordinate, str], verbose: bool = False
) -> int:
    countries: Dict[str, Set[OffsetCoordinate]] = defaultdict(set)
    for coord, cty in assignment.items():
        countries[cty].add(coord)
    min_size = min(len(coords) for coords in countries.values())
    max_size = max(len(coords) for coords in countries.values())
    # better to have a smaller diff between min and max size
    size_score = -(max_size - min_size)
    if verbose:
        print(f"max size {max_size}, min size {min_size}, size score: {size_score}")

    def squareness(cc: Set[OffsetCoordinate]) -> float:
        min_row = min(c.row for c in cc)
        max_row = max(c.row for c in cc)
        min_column = min(c.column for c in cc)
        max_column = max(c.column for c in cc)
        return abs(1.0 - ((max_row - min_row + 1) / (max_column - min_column + 1)))

    squarenesses = [squareness(coords) for coords in countries.values()]
    # this 300 * is just heuristic to give the squareness roughly the
    # same weight as the size, based on observed typical size and squareness
    # values
    squareness_score = -int(300 * sum(squarenesses) / len(squarenesses))  # type: ignore
    if verbose:
        print(
            f"squarenesses: {list(f'{sq:.03f}' for sq in squarenesses)} score: {squareness_score}"
        )
    return size_score + squareness_score
