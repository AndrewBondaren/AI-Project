"""Hydrology domain types — tz_terrain_hydrology.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.application.worldData.generators.climate.climatePoleField import GridBBox
    from app.db.models.namedLocation import NamedLocation


from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.locations.enums.geographicSubtype import (
    GEOGRAPHIC_LOCATION_TYPE,
    GeographicSubtype,
)


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
class LakeSpec:
    shoreline_segments: list[tuple[tuple[int, int], tuple[int, int]]]
    location_uid: str | None = None
    open_water_role: HydrologyCellRole = HydrologyCellRole.LAKE


@dataclass(frozen=True)
class DeclaredRiverEdge:
    edge_uid: str
    segment: tuple[tuple[int, int], tuple[int, int]]
    connection_type: str
    width_cells: int = 1
    location_uid: str | None = None


@dataclass(frozen=True)
class RiverSegment:
    """Classified river piece — declare or autoresolve (U17/U18)."""

    polyline_cells: list[tuple[int, int]]
    connection_type: str
    edge_uid: str | None = None
    location_uid: str | None = None
    declared: bool = False


@dataclass(frozen=True)
class HydrologyMasterInput:
    world_uid:         str
    hydrology_enabled: bool
    scopes:            frozenset[HydrologyScope]
    connection_graph:  LoadedConnectionGraph
    geographic_locations: list[NamedLocation] = field(default_factory=list)
    declared_coastline_segments: list[tuple[tuple[int, int], tuple[int, int]]] = field(
        default_factory=list,
    )
    declared_lake_specs: list[LakeSpec] = field(default_factory=list)
    declared_river_edges: list[DeclaredRiverEdge] = field(default_factory=list)


@dataclass
class HydrologyCellIndex:
    """In-memory surface-top hydrology before column-fill persist."""

    by_cell: dict[tuple[int, int], MapCellHydrology] = field(default_factory=dict)

    @property
    def roles(self) -> dict[tuple[int, int], HydrologyCellRole]:
        return {
            xy: entry.role
            for xy, entry in self.by_cell.items()
            if entry.role is not None
        }


@dataclass
class HydrologyResult:
    heightmap:      Any = None  # SurfaceHeightmap after carve; same ref as input
    cell_index:     HydrologyCellIndex = field(default_factory=HydrologyCellIndex)
    river_segments: list[Any] = field(default_factory=list)
    dirty_bbox:     GridBBox | None = None
    landforms:      Any = None

    @property
    def cells_modified(self) -> int:
        return len(self.cell_index.by_cell)


def resolve_scopes(requested: frozenset[HydrologyScope] | None) -> frozenset[HydrologyScope]:
    if requested is None:
        return HYDROLOGY_BOOTSTRAP_SCOPES
    if HydrologyScope.OPEN_OCEAN in requested and HydrologyScope.COASTAL_SEA not in requested:
        return requested | {HydrologyScope.COASTAL_SEA}
    return requested
