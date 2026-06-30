"""Hydrology domain types — tz_terrain_hydrology.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db.models.namedLocation import NamedLocation


# NamedLocation filter — DB stores type + subtype separately (not "geographic.lake" in one field).
# Docs use combined notation `geographic.lake` = type + subtype; see tz_generator_technical_debt.md HY-GEO-1.
GEOGRAPHIC_LOCATION_TYPE = "geographic"


class GeographicSubtype(StrEnum):
    """system_location_subtype when system_location_type == geographic."""

    MOUNTAIN    = "mountain"
    PEAK        = "peak"
    PLAIN       = "plain"
    LAKE        = "lake"
    SEA         = "sea"
    OCEAN       = "ocean"
    INLAND_SEA  = "inland_sea"
    ISLAND      = "island"
    COAST       = "coast"
    RIVER       = "river"


class HydrologyConnectionType(StrEnum):
    """ConnectionEdge.connection_type values consumed by hydrology declare path."""

    LAKE_SHORELINE  = "lake_shoreline"
    COASTLINE       = "coastline"
    RIVER           = "river"
    MOUNTAIN_RIVER  = "mountain_river"


class HydrologyScope(StrEnum):
    COASTAL_SEA = "coastal_sea"
    OPEN_OCEAN  = "open_ocean"
    LAKES       = "lakes"
    RIVERS      = "rivers"
    LANDFORMS   = "landforms"


HYDROLOGY_BOOTSTRAP_SCOPES = frozenset({
    HydrologyScope.COASTAL_SEA,
    HydrologyScope.OPEN_OCEAN,
    HydrologyScope.LAKES,
    HydrologyScope.RIVERS,
})


class HydrologyCellRole(StrEnum):
    COASTAL_SEA  = "coastal_sea"
    OPEN_OCEAN   = "open_ocean"
    INLAND_SEA   = "inland_sea"
    LAKE         = "lake"
    RIVER_BED    = "river_bed"
    SHORE        = "shore"


@dataclass(frozen=True)
class HydrologyBands:
    min: int
    max: int


@dataclass(frozen=True)
class RiverTypeClassify:
    mountain_min_source_z:        int
    path_mountain_fraction:       float
    rapid_drop_threshold_m:       int
    mountain_bed_steepness_factor: float
    foothill_gradient_threshold:  float


@dataclass(frozen=True)
class ResolvedConnectionNode:
    node_uid:     str
    x_m:          int
    y_m:          int
    z_m:          int
    gx:           int
    gy:           int
    node_type:    str
    graph_level:  str
    location_uid: str | None = None


@dataclass(frozen=True)
class LoadedConnectionGraph:
    nodes: list[ResolvedConnectionNode]
    edges: list[dict]


@dataclass(frozen=True)
class HydrologyMasterInput:
    world_uid:         str
    hydrology_enabled: bool
    scopes:            frozenset[HydrologyScope]
    connection_graph:  LoadedConnectionGraph
    geographic_locations: list[NamedLocation] = field(default_factory=list)


@dataclass
class HydrologyCellIndex:
    """In-memory cell roles/metadata before column-fill persist."""

    roles: dict[tuple[int, int], HydrologyCellRole] = field(default_factory=dict)
    metadata: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)


@dataclass
class HydrologyResult:
    cell_index:     HydrologyCellIndex = field(default_factory=HydrologyCellIndex)
    river_segments: list[Any] = field(default_factory=list)


def resolve_scopes(requested: frozenset[HydrologyScope] | None) -> frozenset[HydrologyScope]:
    if requested is None:
        return HYDROLOGY_BOOTSTRAP_SCOPES
    if HydrologyScope.OPEN_OCEAN in requested and HydrologyScope.COASTAL_SEA not in requested:
        return requested | {HydrologyScope.COASTAL_SEA}
    return requested
