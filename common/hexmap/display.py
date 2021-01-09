from typing import Callable, Dict, List, NamedTuple, Optional, Set, Tuple

from .types import OffsetCoordinate, CubeCoordinate


class DisplayInfo(NamedTuple):
    fill: str
    body1: str
    body2: str


class DrawWindow(NamedTuple):
    min_row: int
    max_row: int
    min_column: int
    max_column: int
    half_top: bool
    half_bottom: bool


class HexInfo(NamedTuple):
    offset: OffsetCoordinate
    cube: CubeCoordinate
    info: DisplayInfo


class HexLookups(NamedTuple):
    by_offset: Dict[OffsetCoordinate, HexInfo]
    by_cube: Dict[CubeCoordinate, HexInfo]


def render_simple(coords: Set[OffsetCoordinate], text_width: int, get_text: Callable[[OffsetCoordinate], Optional[str]], center: Optional[OffsetCoordinate] = None, radius: int = 2) -> List[str]:
    coords, window = _calc_window(coords, center, radius)

    def render_one(row, column, mod):
        rc = OffsetCoordinate(row, column)
        val = get_text(rc) if (column % 2 == mod and rc in coords) else None
        if val is None:
            val = " " * text_width
        return val

    ret = []
    for row in range(window.min_row, window.max_row + 1):
        if row != window.min_row or window.half_top:
            line = ""
            for column in range(window.min_column, window.max_column + 1):
                line += render_one(row, column, 1)
            ret.append(line)
        if row != window.max_row or window.half_bottom:
            line = ""
            for column in range(window.min_column, window.max_column + 1):
                line += render_one(row, column, 0)
            ret.append(line)
    return ret

def render_large(coords: Set[OffsetCoordinate], get_info: Callable[[OffsetCoordinate], Optional[DisplayInfo]], center: Optional[OffsetCoordinate] = None, radius: int = 2) -> List[str]:
# Hexes with a line border, a fill symbol around the edge, and two five-character
# blocks for text in the middle:
#           _ _                 _ _           _ _
#         /* * *\             /* * *\       /• • •\
#    _ _ /*AB 02*\ _ _       /*AB 02*\ _ _ /•AB 04•\
#  /• • •\*12345*/~ ~ ~\     \*12345*/~ ~ ~\• 123 •/
# /•AB 01•\*_*_*/~AB 03~\     \*_*_*/~AB 03~\•_•_•/
# \• 123 •/- - -\~ [C] ~/     /- - -\~ [C] ~/$ $ $\
#  \•_•_•/-AC 02-\~_~_~/     /-AC 02-\~_~_~/$AC 04$\
#  /$ $ $\- -W- -/- - -\     \- -W- -/- - -\$ 789 $/
# /$AC 01$\-_-_-/-AC 03-\     \-_-_-/-AC 03-\$_$_$/
# \$ 789 $/+ + +\- 000 -/     /+ + +\- 000 -/• • •\
#  \$_$_$/+AD 02+\-_-_-/     /+AD 02+\-_-_-/•AD 04•\
#  /• • •\+     +/• • •\     \+     +/• • •\•54321•/
# /•AD 01•\+_+_+/•AD 03•\     \+_+_+/•AD 03•\•_•_•/
# \•54321•/     \•  Z  •/           \•  Z  •/
#  \•_•_•/       \•_•_•/             \•_•_•/
#
    coords, window = _calc_window(coords, center, radius)
    lookups = _make_lookups(coords, get_info)

    # The top border of the hex is written out as the bottom border of the
    # hex above; therefore, we start one row earlier than specified, and
    # draw either just the last line, or the last three lines (the latter
    # if half-top is set). Note that we're using col = 0 (AB 01 / AB 03) in
    # the above diagram for reference, so the col = 1, 3, etc columns actually
    # start printing "above" the official line (hence the first part of this
    # comment about them being printed as part of the previous row).
    ret = []
    for cur_row in range(window.min_row - 1, window.max_row + 1):
        start_line = 1
        if cur_row == window.min_row - 1:
            start_line = 2 if window.half_top else 4

        for line in range(start_line, 5):
            if start_line > line:
                continue
            inv_line = (((line + 1) % 4) + 1)
            txt = ""
            for cur_col in range(window.min_column, window.max_column + 2):
                is_even = (cur_col & 1 == 0)
                cur_line = line if is_even else inv_line
                if cur_col == window.min_column and cur_line in (1, 4):
                    txt += " "
                # remember, we print the second half of odd rows as part of
                # the previous row
                data_row = cur_row if (is_even or cur_line >= 3) else cur_row + 1
                txt += _get_hex_left_border(lookups, data_row, cur_col, cur_line, coords)
                if cur_col <= window.max_column:
                    txt += _get_hex_line(lookups, data_row, cur_col, cur_line, coords)
            if txt.strip():
                ret.append(txt)
    return ret

def _get_hex_line(lookups: HexLookups, row: int, col: int, line: int, coords: Set[OffsetCoordinate]) -> str:
    cur = lookups.by_offset.get(OffsetCoordinate(row, col), None)
    if cur and cur.offset not in coords:
        cur = None
    if line == 1:
        return f"{cur.info.fill} {cur.info.fill} {cur.info.fill}" if cur else (" " * 5)
    elif line == 2:
        return (cur.info.fill + cur.info.body1 + cur.info.fill) if cur else (" " * 7)
    elif line == 3:
        return (cur.info.fill + cur.info.body2 + cur.info.fill) if cur else (" " * 7)
    elif line == 4:
        if cur:
            return f"{cur.info.fill}_{cur.info.fill}_{cur.info.fill}"
        else:
            cur_cube = CubeCoordinate.from_row_col(row, col)
            below = lookups.by_cube.get(cur_cube.step(x_mod=0, y_mod=-1, z_mod=+1), None)
            if below and below.offset not in coords:
                below = None
            return " _ _ " if below else (" " * 5)
    else:
        raise Exception(f"Bad line: {line}")


# that is, the border between the hex at row, cur and the hex to its left
def _get_hex_left_border(lookups: HexLookups, row: int, col: int, line: int, coords: Set[OffsetCoordinate]) -> str:
    cur = lookups.by_offset.get(OffsetCoordinate(row, col), None)
    if cur and cur.offset not in coords:
        cur = None

    cur_cube = CubeCoordinate.from_row_col(row, col)

    left_up = lookups.by_cube.get(cur_cube.step(x_mod=-1, y_mod=+1, z_mod=0), None)
    if left_up and left_up.offset not in coords:
        left_up = None

    left_down = lookups.by_cube.get(cur_cube.step(x_mod=-1, y_mod=0, z_mod=+1), None)
    if left_down and left_down.offset not in coords:
        left_down = None

    if line == 1:
        return "/" if (cur or left_up) else " "
    elif line == 2:
        return "/" if (cur or left_up) else " "
    elif line == 3:
        return "\\" if (cur or left_down) else " "
    elif line == 4:
        return "\\" if (cur or left_down) else " "
    else:
        raise Exception(f"Bad border line: {line}")


def _calc_window(coords: Set[OffsetCoordinate], center: Optional[OffsetCoordinate], radius: int) -> Tuple[Set[OffsetCoordinate], DrawWindow]:
    if center:
        center_cube = CubeCoordinate.from_row_col(center.row, center.column)
        filtered = set()
        for coord in coords:
            cube = CubeCoordinate.from_row_col(coord.row, coord.column)
            if cube.distance(center_cube) <= radius:
                filtered.add(coord)
        coords = filtered

    min_row = min(x.row for x in coords)
    max_row = max(x.row for x in coords)
    return coords, DrawWindow(
        min_row=min_row,
        max_row=max_row,
        min_column=min(x.column for x in coords),
        max_column=max(x.column for x in coords),
        half_top=any(x.column % 2 == 1 for x in coords if x.row == min_row),
        half_bottom=any(x.column % 2 == 0 for x in coords if x.row == max_row),
    )

def _make_lookups(coords: Set[OffsetCoordinate], get_info: Callable[[OffsetCoordinate], Optional[DisplayInfo]]) -> HexLookups:
    lst = []
    for coord in coords:
        info = get_info(coord)
        if info is None:
            continue
        cube = CubeCoordinate.from_row_col(coord.row, coord.column)
        lst.append(HexInfo(offset=coord, cube=cube, info=info))

    return HexLookups(
        by_offset={hx.offset: hx for hx in lst},
        by_cube={hx.cube: hx for hx in lst}
    )
