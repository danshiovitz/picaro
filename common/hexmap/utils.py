from dataclasses import dataclass
from typing import Dict, List, Set

from .types import CubeCoordinate, OffsetCoordinate


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


@dataclass(frozen=True)
class FloatCube:
    x: float
    y: float
    z: float

    @classmethod
    def from_cube(cls, cube: CubeCoordinate, epsilon: bool = False) -> "FloatCube":
        if epsilon:
            return FloatCube(
                float(cube.x + 1e-6), float(cube.y + 2e-6), float(cube.z + -3e-6)
            )
        return FloatCube(float(cube.x), float(cube.y), float(cube.z))

    def to_cube(self) -> CubeCoordinate:
        # as https://www.redblobgames.com/grids/hexagons/#rounding
        rx = round(self.x)
        ry = round(self.y)
        rz = round(self.z)

        x_diff = abs(rx - self.x)
        y_diff = abs(ry - self.y)
        z_diff = abs(rz - self.z)

        if x_diff > y_diff and x_diff > z_diff:
            rx = -ry - rz
        elif y_diff > z_diff:
            ry = -rx - rz
        else:
            rz = -rx - ry

        return CubeCoordinate(rx, ry, rz)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def cube_lerp(a: FloatCube, b: FloatCube, t: float) -> FloatCube:
    return FloatCube(lerp(a.x, b.x, t), lerp(a.y, b.y, t), lerp(a.z, b.z, t))


def cube_linedraw(a: CubeCoordinate, b: CubeCoordinate) -> List[CubeCoordinate]:
    if a == b:
        return []
    dist = a.distance(b)
    results: List[CubeCoordinate] = []
    af = FloatCube.from_cube(a, epsilon=True)
    bf = FloatCube.from_cube(b, epsilon=False)
    for i in range(dist + 1):
        results.append(cube_lerp(af, bf, 1.0 / dist * i).to_cube())
    return results
