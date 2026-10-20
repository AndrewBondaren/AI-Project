"""Unrolled world fine-cell geometry; edge noise belongs to rasterization."""

from __future__ import annotations

from enum import StrEnum
from math import ceil, floor, pi, sqrt
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

class RegionShapeKind(StrEnum):
    BBOX = "bbox"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    ANCHOR_RADIUS = "anchor_radius"
    CORRIDOR = "corridor"


Point = tuple[int, int]
Bounds = tuple[int, int, int, int]


def _cross(a: Point, b: Point, c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: tuple[float, float]) -> bool:
    return (_cross(a, b, p) == 0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
    cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
    return ((ab_c * ab_d < 0 and cd_a * cd_b < 0)
            or _on_segment(a, b, c) or _on_segment(a, b, d)
            or _on_segment(c, d, a) or _on_segment(c, d, b))


class EdgeNoise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amplitude: int = Field(ge=0)
    scale: int = Field(gt=0)


class RegionShapeBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_noise: EdgeNoise | None = None


class BboxShape(RegionShapeBase):
    kind: Literal[RegionShapeKind.BBOX] = RegionShapeKind.BBOX
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if self.x_max < self.x_min or self.y_max < self.y_min:
            raise ValueError("bbox requires x_min <= x_max and y_min <= y_max")
        return self

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def bbox(self) -> Bounds:
        return self.x_min, self.y_min, self.x_max, self.y_max

    def area(self) -> float:
        # Coverage cells matching inclusive contains(): a 1x1 bbox covers 1.
        return float((self.x_max - self.x_min + 1) * (self.y_max - self.y_min + 1))


class EllipseShape(RegionShapeBase):
    kind: Literal[RegionShapeKind.ELLIPSE] = RegionShapeKind.ELLIPSE
    cx: int
    cy: int
    rx: int = Field(gt=0)
    ry: int = Field(gt=0)

    def contains(self, x: float, y: float) -> bool:
        return ((x - self.cx) / self.rx) ** 2 + ((y - self.cy) / self.ry) ** 2 <= 1

    def bbox(self) -> Bounds:
        return self.cx - self.rx, self.cy - self.ry, self.cx + self.rx, self.cy + self.ry

    def area(self) -> float:
        return pi * self.rx * self.ry


class PolygonShape(RegionShapeBase):
    """Simple closed ring; last-to-first edge is implicit or explicitly repeated."""

    kind: Literal[RegionShapeKind.POLYGON] = RegionShapeKind.POLYGON
    vertices: list[Point] = Field(min_length=3)

    def _ring(self) -> list[Point]:
        return self.vertices[:-1] if self.vertices[0] == self.vertices[-1] else self.vertices

    @model_validator(mode="after")
    def simple_ring(self) -> Self:
        ring = self._ring()
        n = len(ring)
        if n < 3 or len(set(ring)) != n:
            raise ValueError("polygon requires at least three distinct vertices")
        edges = list(zip(ring, ring[1:] + ring[:1]))
        for i, (a, b) in enumerate(edges):
            c = ring[(i + 2) % n]
            if _cross(a, b, c) == 0 and (
                (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > 0
            ):
                raise ValueError("polygon adjacent edges overlap")
            for j in range(i + 1, n):
                if j == i + 1 or (i == 0 and j == n - 1):
                    continue
                if _intersects(a, b, *edges[j]):
                    raise ValueError("polygon must not self-intersect")
        if self.area() == 0:
            raise ValueError("polygon must have nonzero area")
        return self

    def contains(self, x: float, y: float) -> bool:
        ring = self._ring()
        inside = False
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if _on_segment(a, b, (x, y)):
                return True
            if (a[1] > y) != (b[1] > y):
                crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if x < crossing_x:
                    inside = not inside
        return inside

    def bbox(self) -> Bounds:
        xs, ys = zip(*self.vertices)
        return min(xs), min(ys), max(xs), max(ys)

    def area(self) -> float:
        ring = self._ring()
        return abs(sum(a[0] * b[1] - b[0] * a[1]
                       for a, b in zip(ring, ring[1:] + ring[:1]))) / 2


class AnchorRadiusShape(RegionShapeBase):
    """Unresolved anchor reference; collect resolves it to absolute geometry."""

    kind: Literal[RegionShapeKind.ANCHOR_RADIUS] = RegionShapeKind.ANCHOR_RADIUS
    anchor_uid: str = Field(min_length=1)
    radius: int = Field(gt=0)

    def contains(self, x: float, y: float) -> bool:
        raise ValueError("anchor_radius must be resolved in collect before contains")

    def bbox(self) -> Bounds:
        raise ValueError("anchor_radius must be resolved in collect before bbox")

    def area(self) -> float:
        return pi * self.radius ** 2


class CorridorShape(RegionShapeBase):
    """Union of round-capped segments in one authored unrolled frame."""

    kind: Literal[RegionShapeKind.CORRIDOR] = RegionShapeKind.CORRIDOR
    path: list[Point] = Field(min_length=2)
    width: int = Field(gt=0)

    @model_validator(mode="after")
    def nonzero_path(self) -> Self:
        if len(set(self.path)) < 2:
            raise ValueError("corridor requires at least two distinct points")
        return self

    def distance(self, x: float, y: float) -> float:
        from app.dataModel.topology.corridorGeometry import polyline_distance2
        return sqrt(polyline_distance2((x, y), self.path))

    def contains(self, x: float, y: float) -> bool:
        return self.distance(x, y) <= self.width / 2

    def bbox(self) -> Bounds:
        xs, ys = zip(*self.path)
        radius = self.width / 2
        return (floor(min(xs) - radius), floor(min(ys) - radius),
                ceil(max(xs) + radius), ceil(max(ys) + radius))

    def area(self) -> float:
        from app.dataModel.topology.corridorGeometry import corridor_area
        return corridor_area(tuple(self.path), self.width)


RegionShape = Annotated[
    BboxShape | EllipseShape | PolygonShape | AnchorRadiusShape | CorridorShape,
    Field(discriminator="kind"),
]
