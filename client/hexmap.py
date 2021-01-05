from string import ascii_uppercase
from typing import Dict, NamedTuple, Optional, Set, Tuple

from colors import colors

# def render(self, selected):
#     reg_fmt = self.terrain.fmt
#     inv_fmt = colors.fg.black + self.terrain.bg_fmt
#     if self.features:
#         sym = list(self.features.values())[0].symbol
#         return inv_fmt + sym + colors.reset
#     elif selected:
#         return inv_fmt + self.terrain.symbol + colors.reset
#     else:
#         return reg_fmt + self.terrain.symbol + colors.reset

# buncha stuff from https://www.redblobgames.com/grids/hexagons per usual
# clean-room reimpl of the hex design from https://github.com/cmelchior/asciihexgrid

class OffsetCoordinate(NamedTuple):
    row: int
    col: int


class CubeCoordinate(NamedTuple):
    x: int
    y: int
    z: int

    @classmethod
    def from_row_col(cls, row: int, col: int) -> "CubeCoordinate":
        x = col
        z = row - (col + (col&1)) // 2
        y = -x - z
        return CubeCoordinate(x=x, y=y, z=z)

    def distance(self, other: "CubeCoordinate") -> int:
        return (abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)) // 2

    def step(self, x_mod: int, y_mod: int, z_mod: int) -> "CubeCoordinate":
        return CubeCoordinate(x=self.x + x_mod, y=self.y + y_mod, z=self.z + z_mod)

class Hex(NamedTuple):
    offset: OffsetCoordinate
    cube: CubeCoordinate
    name: str
    fill: str
    body: str


class Hexmap(NamedTuple):
    by_name: Dict[str, Hex]
    by_offset: Dict[OffsetCoordinate, Hex]
    by_cube: Dict[CubeCoordinate, Hex]
    num_rows: int
    num_cols: int


class DrawWindow(NamedTuple):
    min_row: int
    max_row: int
    min_col: int
    max_col: int
    half_top: bool
    half_bottom: bool


def draw_small(hexmap: Hexmap, dot: bool, to_draw: Optional[Set[OffsetCoordinate]] = None) -> None:
    if not to_draw:
        to_draw = set(hexmap.by_offset)
    window = calc_window(hexmap, to_draw)

    def draw_one(row, col, mod):
        cur = hexmap.by_offset.get(OffsetCoordinate(row, col), None)
        if dot:
            val = "." if cur else " "
        else:
            val = center_pad(cur.name if cur else "", 5)
        if col % 2 != mod or (row, col) not in to_draw:
            val = "".join(" " for c in val)
        print(val, end="")

    for row in range(window.min_row, window.max_row + 1):
        if row != window.min_row or window.half_top:
            for col in range(window.min_col, window.max_col + 1):
                draw_one(row, col, 1)
            print()
        if row != window.max_row or window.half_bottom:
            for col in range(window.min_col, window.max_col + 1):
                draw_one(row, col, 0)
            print()


def draw_large(hexmap: Hexmap, to_draw: Optional[Set[OffsetCoordinate]] = None) -> None:
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
    if not to_draw:
        to_draw = set(hexmap.by_offset)
    window = calc_window(hexmap, to_draw)

    # The top border of the hex is written out as the bottom border of the
    # hex above; therefore, we start one row earlier than specified, and
    # draw either just the last line, or the last three lines (the latter
    # if half-top is set). Note that we're using col = 0 (AB 01 / AB 03) in
    # the above diagram for reference, so the col = 1, 3, etc columns actually
    # start printing "above" the official line (hence the first part of this
    # comment about them being printed as part of the previous row).
    for cur_row in range(window.min_row - 1, window.max_row + 1):
        start_line = 1
        if cur_row == window.min_row - 1:
            start_line = 2 if window.half_top else 4

        for line in range(start_line, 5):
            if start_line > line:
                continue
            inv_line = (((line + 1) % 4) + 1)
            txt = ""
            for cur_col in range(window.min_col, window.max_col + 2):
                is_even = (cur_col & 1 == 0)
                cur_line = line if is_even else inv_line
                if cur_col == window.min_col and cur_line in (1, 4):
                    txt += " "
                # remember, we print the second half of odd rows as part of
                # the previous row
                data_row = cur_row if (is_even or cur_line >= 3) else cur_row + 1
                txt += get_hex_left_border(hexmap, data_row, cur_col, cur_line, to_draw)
                if cur_col <= window.max_col:
                    txt += get_hex_line(hexmap, data_row, cur_col, cur_line, to_draw)
            if txt.strip():
                print(txt)


def get_hex_line(hexmap: Hexmap, row: int, col: int, line: int, to_draw: Set[OffsetCoordinate]) -> str:
    cur = hexmap.by_offset.get(OffsetCoordinate(row, col), None)
    if cur and cur.offset not in to_draw:
        cur = None
    if line == 1:
        return f"{cur.fill} {cur.fill} {cur.fill}" if cur else (" " * 5)
    elif line == 2:
        return (cur.fill + center_pad(cur.name, 5) + cur.fill) if cur else (" " * 7)
    elif line == 3:
        return (cur.fill + center_pad(cur.body, 5) + cur.fill) if cur else (" " * 7)
    elif line == 4:
        if cur:
            return f"{cur.fill}_{cur.fill}_{cur.fill}"
        else:
            cur_cube = CubeCoordinate.from_row_col(row, col)
            below = hexmap.by_cube.get(cur_cube.step(x_mod=0, y_mod=-1, z_mod=+1), None)
            if below and below.offset not in to_draw:
                below = None
            return " _ _ " if below else (" " * 5)
    else:
        raise Exception(f"Bad line: {line}")


# that is, the border between the hex at row, cur and the hex to its left
def get_hex_left_border(hexmap: Hexmap, row: int, col: int, line: int, to_draw: Set[OffsetCoordinate]) -> str:
    cur = hexmap.by_offset.get(OffsetCoordinate(row, col), None)
    if cur and cur.offset not in to_draw:
        cur = None

    cur_cube = CubeCoordinate.from_row_col(row, col)

    left_up = hexmap.by_cube.get(cur_cube.step(x_mod=-1, y_mod=+1, z_mod=0), None)
    if left_up and left_up.offset not in to_draw:
        left_up = None

    left_down = hexmap.by_cube.get(cur_cube.step(x_mod=-1, y_mod=0, z_mod=+1), None)
    if left_down and left_down.offset not in to_draw:
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


def center_pad(val: str, size: int) -> str:
    flag = False
    while len(val) < size:
        if flag:
            val = " " + val
        else:
            val += " "
        flag = not flag
    return val


def calc_window(hexmap: Hexmap, to_draw: Set[OffsetCoordinate]) -> DrawWindow:
    min_row = min(x.row for x in to_draw)
    max_row = max(x.row for x in to_draw)
    return DrawWindow(
        min_row=min_row,
        max_row=max_row,
        min_col=min(x.col for x in to_draw),
        max_col=max(x.col for x in to_draw),
        half_top=any(x.col % 2 == 1 for x in to_draw if x.row == min_row),
        half_bottom=any(x.col % 2 == 0 for x in to_draw if x.row == max_row),
    )


def rectangle(hexmap: Hexmap, mins: OffsetCoordinate, maxes: OffsetCoordinate) -> Set[OffsetCoordinate]:
    return {hh.offset for offset, hh in hexmap.by_offset.items() if (
        mins.row <= offset.row <= maxes.row and
        mins.col <= offset.col <= maxes.col
    )}


def circle(hexmap: Hexmap, center: OffsetCoordinate, radius: int) -> Set[OffsetCoordinate]:
    center_cube = CubeCoordinate.from_row_col(center.row, center.col)

    return {hh.offset for cube, hh in hexmap.by_cube.items() if (
        center_cube.distance(hh.cube) <= radius
    )}


def make_hexmap(num_rows: int, num_cols: int) -> Hexmap:
    hexes = []
    for row in range(0, num_rows):
        for col in range(0, num_cols):
            rn = ascii_uppercase[row // 26] + ascii_uppercase[row % 26]
            nm = f"{rn}{col+1:02}"
            fill = "~"
            body = "***"
            offset = OffsetCoordinate(row=row, col=col)
            cube = CubeCoordinate.from_row_col(row=row, col=col)
            hh = Hex(offset=offset, cube=cube, name=nm, fill=fill, body=body)
            hexes.append(hh)
    return Hexmap(
        by_name={hh.name: hh for hh in hexes},
        by_offset={hh.offset: hh for hh in hexes},
        by_cube={hh.cube: hh for hh in hexes},
        num_rows=num_rows,
        num_cols=num_cols
    )


if __name__ == "__main__":
    hm = make_hexmap(5, 5)
    draw_small(hm, dot=False)
    draw_large(hm)
    draw_large(hm, rectangle(hm, OffsetCoordinate(1, 1), OffsetCoordinate(2, 4)))
    draw_large(hm, rectangle(hm, OffsetCoordinate(1, 0), OffsetCoordinate(2, 4)))
    draw_large(hm, {OffsetCoordinate(0, 0), OffsetCoordinate(1, 0), OffsetCoordinate(0, 2), OffsetCoordinate(0, 3), OffsetCoordinate(3, 2)})
    print("======")
    draw_large(hm, {OffsetCoordinate(0, 0)})
    print("======")
    draw_large(hm, {OffsetCoordinate(0, 1)})
    print("======")
