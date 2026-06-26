from dataclasses import dataclass
from typing import NewType

GridX = NewType("GridX", int)
GridY = NewType("GridY", int)
MeterX = NewType("MeterX", int)
MeterY = NewType("MeterY", int)
MeterZ = NewType("MeterZ", int)


@dataclass(frozen=True, slots=True)
class SurfaceGridCoord:
    gx: GridX
    gy: GridY


@dataclass(frozen=True, slots=True)
class LocalMeterCoord:
    x: MeterX
    y: MeterY
    z: MeterZ


@dataclass(frozen=True, slots=True)
class SurfaceGridRect:
    gx0: GridX
    gy0: GridY
    gx1: GridX
    gy1: GridY

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.gx0, self.gy0, self.gx1, self.gy1


@dataclass(frozen=True, slots=True)
class LocalMeterRect:
    x0: MeterX
    y0: MeterY
    x1: MeterX
    y1: MeterY
    z: MeterZ

    def as_tuple(self) -> tuple[int, int, int, int, int]:
        return self.x0, self.y0, self.x1, self.y1, self.z
