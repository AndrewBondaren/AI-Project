"""Runtime ridge graph types — tz_mountain_architecture (not wire)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.dataModel.terrainMasks.mountain.specs import MountainSpec


class RidgeSegmentContext(StrEnum):
    PRIMARY_MST_EDGE = "primary_mst_edge"
    SPUR_FROM_PEAK = "spur_from_peak"
    FOOTHILL = "foothill"


@dataclass(frozen=True, slots=True)
class RidgeVertex:
    index: int
    x_m: float
    y_m: float
    peak: MountainSpec
    hat_radius_m: float | None = None


@dataclass(frozen=True, slots=True)
class RidgeEdge:
    a: int
    b: int
    length_m: float


@dataclass(frozen=True, slots=True)
class RidgeGraph:
    vertices: tuple[RidgeVertex, ...]
    edges: tuple[RidgeEdge, ...]  # MST (or Delaunay before MST)


@dataclass(frozen=True, slots=True)
class MountainSystem:
    """Cluster of summit anchors that form one peak or one range."""

    vertices: tuple[RidgeVertex, ...]
    peak_gap_m: float


@dataclass(frozen=True, slots=True)
class BuiltSegment:
    """Internal: primary or secondary range + optional parent vertex indices."""

    context: RidgeSegmentContext
    peaks: tuple[MountainSpec, ...]
    spine: tuple[tuple[int, int], ...]
    width_m: int
    mst_edges: tuple[RidgeEdge, ...] = field(default_factory=tuple)
