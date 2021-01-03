import random
from dataclasses import dataclass
from enum import Enum
from string import ascii_uppercase
from typing import Dict, Optional, Tuple

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

@dataclass
class Hex:
    row: int
    col: int
    name: str
    fill: str
    body: str


@dataclass
class Hexmap:
    hexes_by_name: Dict[str, Hex]
    hexes_by_coord: Dict[Tuple[int, int], Hex]
    num_rows: int
    num_cols: int


def make_hexmap(num_rows: int, num_cols: int) -> Hexmap:
    by_name = {}
    by_coord = {}
    for row in range(0, num_rows):
        for col in range(0, num_cols):
            rn = ascii_uppercase[row // 26] + ascii_uppercase[row % 26]
            nm = f"{rn}{col+1:02}"
            fill = "~"
            body = "***"
            hh = Hex(row=row, col=col, name=nm, fill=fill, body=body)
            by_name[hh.name] = hh
            by_coord[(row, col)] = hh
    return Hexmap(hexes_by_name=by_name, hexes_by_coord=by_coord, num_rows=num_rows, num_cols=num_cols)


def draw_very_small(hexmap: Hexmap, center: Optional[Tuple[int, int]] = None, radius: Optional[int] = None) -> None:
    from_row, to_row, from_col, to_col = calc_window(hexmap, center, radius)
    top_fmt = " ."
    bottom_fmt = ". "
    top_from = from_col + 1
    bottom_from = from_col
    if from_col % 2 == 1:
        top_fmt, bottom_fmt = bottom_fmt, top_fmt
        top_from -= 1
        bottom_from += 1
    for row in range(from_row, to_row + 1):
        for col in range(top_from, to_col + 1, 2):
            print(top_fmt, end="")
        print()
        for col in range(bottom_from, to_col + 1, 2):
            print(bottom_fmt, end="")
        print()


def draw_small(hexmap: Hexmap, center: Optional[Tuple[int, int]] = None, radius: Optional[int] = None) -> None:
    from_row, to_row, from_col, to_col = calc_window(hexmap, center, radius)
    top_fmt = "    {}"
    bottom_fmt = "{}    "
    top_from = from_col + 1
    bottom_from = from_col
    if from_col % 2 == 1:
        top_fmt, bottom_fmt = bottom_fmt, top_fmt
        top_from -= 1
        bottom_from += 1
    for row in range(from_row, to_row + 1):
        for col in range(top_from, to_col + 1, 2):
            nm = hexmap.hexes_by_coord[(row, col)].name
            print(top_fmt.format(nm), end="")
        print()
        for col in range(bottom_from, to_col + 1, 2):
            nm = hexmap.hexes_by_coord[(row, col)].name
            print(bottom_fmt.format(nm), end="")
        print()


def draw_large(hexmap: Hexmap, center: Optional[Tuple[int, int]] = None, radius: Optional[int] = None) -> None:
    from_row, to_row, from_col, to_col = calc_window(hexmap, center, radius)
    for cur_row in range(from_row, to_row + 1):
        draw_large_row(hexmap, cur_row, cur_row == from_row, cur_row == to_row, from_col, to_col)


def draw_large_row(hexmap: Hexmap, row: int, is_top: bool, is_bottom: bool, from_col: int, to_col: int) -> None:
    #    _ _           _ _
    if is_top:
        for cur_col in range(from_col, to_col + 1):
            if cur_col % 2 == 1:
                if cur_col == from_col:
                    print(" " * 2, end="")
                print(get_hex_line_top(hexmap, row, cur_col), end="")
            else:
                print(" " * 9, end="")
        print()

    #   /* * *\       /• • •\
    #  \• 123 •/- - -\~ [C] ~/
    for cur_col in range(from_col, to_col + 1):
        if cur_col % 2 == 1:
            if cur_col == from_col:
                print(" /", end="")
            print(get_hex_line_1(hexmap, row, cur_col), end="")
        else:
            if is_top:
                print(" " * 7, end="")
                if cur_col == from_col:
                    print(" ", end="")
                if cur_col != to_col:
                    print("/", end="")
            else:
                if cur_col == from_col:
                    print("\\", end="")
                print(get_hex_line_3(hexmap, row, cur_col), end="")
    print()

    #    _ _ /*AB 02*\ _ _
    # /-AC 02-\~_~_~/$AC 04$\
    for cur_col in range(from_col, to_col + 1):
        if cur_col % 2 == 1:
            if cur_col == from_col:
                print("/", end="")
            print(get_hex_line_2(hexmap, row, cur_col), end="")
        else:
            if is_top:
                if cur_col == from_col:
                    print(" " * 2, end="")
                print(get_hex_line_top(hexmap, row, cur_col), end="")
                if cur_col != to_col:
                    print("/", end="")
            else:
                if cur_col == from_col:
                    print(" \\", end="")
                print(get_hex_line_4(hexmap, row, cur_col), end="")
    print()

    #  /• • •\*12345*/~ ~ ~\
    # \*12345*/~ ~ ~\• 123 •/
    for cur_col in range(from_col, to_col + 1):
        if cur_col % 2 == 1:
            if cur_col == from_col:
                print("\\", end="")
            print(get_hex_line_3(hexmap, row, cur_col), end="")
        else:
            if cur_col == from_col:
                print(" /", end="")
            print(get_hex_line_1(hexmap, row, cur_col), end="")
    print()

    # /•AB 01•\*_*_*/~AB 03~\
    #  \*_*_*/~AB 03~\•_•_•/
    for cur_col in range(from_col, to_col + 1):
        if cur_col % 2 == 1:
            if cur_col == from_col:
                print(" \\", end="")
            print(get_hex_line_4(hexmap, row, cur_col), end="")
        else:
            if cur_col == from_col:
                print("/", end="")
            print(get_hex_line_2(hexmap, row, cur_col), end="")
    print()

    if is_bottom:
        # need to finish out the last row
        for cur_col in range(from_col, to_col + 1):
            if cur_col % 2 == 1:
                print(" " * 5, end="")
                if cur_col == from_col:
                    print(" ", end="")
                if cur_col != to_col:
                    print("\\", end="")
            else:
                if cur_col == from_col:
                    print("\\", end="")
                print(get_hex_line_3(hexmap, row, cur_col), end="")
        print()

        for cur_col in range(from_col, to_col + 1):
            if cur_col % 2 == 1:
                print(" " * 7, end="")
                if cur_col == from_col:
                    print(" ", end="")
                if cur_col != to_col:
                    print("\\", end="")
            else:
                if cur_col == from_col:
                    print(" \\", end="")
                print(get_hex_line_4(hexmap, row, cur_col), end="")
        print()


#           _ _
#         /* * *\
#    _ _ /*AB 02*\ _ _
#  /• • •\*12345*/~ ~ ~\
# /•AB 01•\*_*_*/~AB 03~\
# \• 123 •/- - -\~ [C] ~/
#  \•_•_•/-AC 02-\~_~_~/
#  /$ $ $\- -W- -/- - -\
# /$AC 01$\-_-_-/-AC 03-\
# \$ 789 $/+ + +\- 000 -/
#  \$_$_$/+AD 02+\-_-_-/
#  /• • •\+     +/• • •\
# /•AD 01•\+_+_+/•AD 03•\
# \•54321•/     \•  Z  •/
#  \•_•_•/       \•_•_•/
#
#    _ _           _ _
#  /* * *\       /• • •\
# /*AB 02*\ _ _ /•AB 04•\
# \*12345*/~ ~ ~\• 123 •/
#  \*_*_*/~AB 03~\•_•_•/
#  /- - -\~ [C] ~/$ $ $\
# /-AC 02-\~_~_~/$AC 04$\
# \- -W- -/- - -\$ 789 $/
#  \-_-_-/-AC 03-\$_$_$/
#  /+ + +\- 000 -/• • •\
# /+AD 02+\-_-_-/•AD 04•\
# \+     +/• • •\•54321•/
#  \+_+_+/•AD 03•\•_•_•/
#        \•  Z  •/
#         \•_•_•/


def get_hex_line_top(hexmap: Hexmap, row: int, col: int) -> str:
    return " _ _ "


def get_hex_line_1(hexmap: Hexmap, row: int, col: int) -> str:
    cur = hexmap.hexes_by_coord.get((row, col))
    return f"{cur.fill} {cur.fill} {cur.fill}\\"


def get_hex_line_2(hexmap: Hexmap, row: int, col: int) -> str:
    cur = hexmap.hexes_by_coord.get((row, col))
    return cur.fill + center_pad(cur.name, 5) + cur.fill + "\\"


def get_hex_line_3(hexmap: Hexmap, row: int, col: int) -> str:
    cur = hexmap.hexes_by_coord.get((row, col))
    return cur.fill + center_pad(cur.body, 5) + cur.fill + "/"


def get_hex_line_4(hexmap: Hexmap, row: int, col: int) -> str:
    cur = hexmap.hexes_by_coord.get((row, col))
    return f"{cur.fill}_{cur.fill}_{cur.fill}/"


def center_pad(val: str, size: int) -> str:
    flag = False
    while len(val) < size:
        if flag:
            val = " " + val
        else:
            val += " "
        flag = not flag
    return val


def calc_window(hexmap: Hexmap, center: Optional[Tuple[int, int]], radius: Optional[int]) -> Tuple[int, int, int, int]:
    if center:
        center_row, center_col = center
    else:
        center_row = hexmap.num_rows // 2
        center_col = hexmap.num_cols // 2
    if radius is None:
        radius = max(hexmap.num_rows, hexmap.num_cols)
    return (max(center_row - radius, 0),
            min(center_row + radius, hexmap.num_rows - 1),
            max(center_col - radius, 0),
            min(center_col + radius, hexmap.num_cols - 1))


if __name__ == "__main__":
    hm = make_hexmap(30, 30)
    # draw_very_small(hm)
    # draw_very_small(hm, center=(5, 5), radius=3)
    draw_large(hm, center=(2, 2), radius=2)
