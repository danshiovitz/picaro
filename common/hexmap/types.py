from dataclasses import dataclass
from string import ascii_uppercase


@dataclass(frozen=True)
class OffsetCoordinate:
    row: int
    column: int

    def get_name(self) -> str:
        rn = ascii_uppercase[self.row // 26] + ascii_uppercase[self.row % 26]
        return f"{rn}{self.column+1:02}"


@dataclass(frozen=True)
class CubeCoordinate:
    x: int
    y: int
    z: int

    @classmethod
    def from_row_col(cls, row: int, col: int) -> "CubeCoordinate":
        x = col
        z = row - (col + (col & 1)) // 2
        y = -x - z
        return CubeCoordinate(x=x, y=y, z=z)

    @classmethod
    def from_offset(cls, offset: OffsetCoordinate) -> "CubeCoordinate":
        return cls.from_row_col(row=offset.row, col=offset.column)

    def to_offset(self) -> OffsetCoordinate:
        row = self.z + (self.x + (self.x & 1)) // 2
        column = self.x
        return OffsetCoordinate(row, column)

    def distance(self, other: "CubeCoordinate") -> int:
        return (
            abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)
        ) // 2

    def step(self, x_mod: int, y_mod: int, z_mod: int) -> "CubeCoordinate":
        return CubeCoordinate(x=self.x + x_mod, y=self.y + y_mod, z=self.z + z_mod)
