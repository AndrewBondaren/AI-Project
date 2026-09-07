from dataclasses import dataclass
from typing import NewType

GridX = NewType("GridX", int)
GridY = NewType("GridY", int)
FineX = NewType("FineX", int)
FineY = NewType("FineY", int)
FineZ = NewType("FineZ", int)
FineDelta = NewType("FineDelta", int)


@dataclass(frozen=True, slots=True)
class SurfaceGridCoord:
    gx: GridX
    gy: GridY


@dataclass(frozen=True, slots=True)
class FineGridCoord:
    x: FineX
    y: FineY
    z: FineZ


@dataclass(frozen=True, slots=True)
class SurfaceGridRect:
    gx0: GridX
    gy0: GridY
    gx1: GridX
    gy1: GridY

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.gx0, self.gy0, self.gx1, self.gy1


@dataclass(frozen=True, slots=True)
class FineGridRect:
    x0: FineX
    y0: FineY
    x1: FineX
    y1: FineY
    z: FineZ

    def as_tuple(self) -> tuple[int, int, int, int, int]:
        return self.x0, self.y0, self.x1, self.y1, self.z
