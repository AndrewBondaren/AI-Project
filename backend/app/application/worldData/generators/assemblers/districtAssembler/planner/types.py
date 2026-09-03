"""Runtime packing types — not wire. C22 district planting."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate

Rect = tuple[int, int, int, int]

# C21 courtyard pad — not an alley. Packing and AreaSlot share this value.
YARD_PADDING_M = 1


@dataclass(frozen=True)
class InnerBBox:
    """Exclusive-max AABB in WORLD_LOCAL_METERS (1 cell = 1 m)."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def as_rect(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class Lattice:
    """Axis lines; origin = inner origin; step from DistrictDensity. No stretch."""

    xs: tuple[int, ...]
    ys: tuple[int, ...]
    step: int

    @property
    def n_cols(self) -> int:
        return len(self.xs)

    @property
    def n_rows(self) -> int:
        return len(self.ys)

    def module_count_x(self) -> int:
        return max(0, len(self.xs) - 1)

    def module_count_y(self) -> int:
        return max(0, len(self.ys) - 1)

    def module_rect(self, col: int, row: int, dc: int = 1, dr: int = 1) -> tuple[int, int, int, int]:
        return (
            self.xs[col],
            self.ys[row],
            self.xs[col + dc],
            self.ys[row + dr],
        )


@dataclass(frozen=True)
class PackingToken:
    uid: str
    system_name: str
    w: int
    h: int
    priority: int
    required: bool
    position: str | None
    copy_index: int
    n_from: str


@dataclass(frozen=True)
class Reservation:
    token: PackingToken
    col: int
    row: int
    span_cols: int
    span_rows: int
    rect_xy: tuple[int, int, int, int]
    rotated_90: bool
    pass_id: int


@dataclass
class Hole:
    col: int
    row: int
    rect: tuple[int, int, int, int]
    free: list[tuple[int, int, int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class StreetFrameContext:
    inner: InnerBBox
    step: int
    blocked_rects: tuple[tuple[int, int, int, int], ...]
    corridor_rects: tuple[tuple[int, int, int, int], ...]


@dataclass
class AreaPlacement:
    area_slot: AreaSlot
    template: BuildingLayoutTemplate
    building_x: int
    building_y: int
    facing: Facing = Facing.SOUTH
    reservation: Reservation | None = None
