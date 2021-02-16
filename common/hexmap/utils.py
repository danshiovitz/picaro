from typing import Dict, Set

from .types import OffsetCoordinate


def calc_offset_neighbor_map(
    num_rows: int, num_columns: int
) -> Dict[OffsetCoordinate, Set[OffsetCoordinate]]:
    ret = {}
    # per https://www.redblobgames.com/grids/hexagons/
    # but we flip row/col
    evenq_directions = [
        [[+1, +1], [0, +1], [-1, 0], [0, -1], [+1, -1], [+1, 0]],
        [[0, +1], [-1, +1], [-1, 0], [-1, -1], [0, -1], [+1, 0]],
    ]
    for row in range(0, num_rows):
        for col in range(0, num_columns):
            ret[OffsetCoordinate(row=row, column=col)] = {
                OffsetCoordinate(row=row + dir[0], column=col + dir[1])
                for dir in evenq_directions[col & 1]
                if (0 <= (row + dir[0]) < num_rows)
                and (0 <= (col + dir[1]) < num_columns)
            }
    return ret
