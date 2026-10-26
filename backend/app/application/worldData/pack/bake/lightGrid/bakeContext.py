"""Caller contract for L0 light compose — tz_map_light_bake."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry

from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.dataModel.worldPack.wire.paintedRoadEdge import PaintedRoadEdge
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


@dataclass
class LightGridBakeContext:
    world: World
    locations: list[NamedLocation]
    locations_index: LocationsIndexWire
    tiles: list[tuple[int, int]]
    scale: LightGridScale
    nodes: list[ConnectionNode] = field(default_factory=list)
    edges: list[ConnectionEdge] = field(default_factory=list)
    # Migration-only observation channel until PC-11.7; frozen consumers use working.
    surface_planning: SurfaceTerrainContext | None = None
    surface_bundle: SurfacePlanBundle | None = None
    working: SurfaceWorkingMaps | None = None
    # Resolved once by the operation owner at ctx construction; landcover inputs
    # consume them instead of running their own world-scoped resolve per tile.
    topology: WorldTopology | None = None
    grid: SurfaceGridSettings | None = None
    pole_field: ClimatePoleField | None = None
    terrain_system_keys: set[str] = field(default_factory=set)
    wilderness_region_entries: list[WildernessRegionEntry] = field(default_factory=list)
    region_state_snapshot: Mapping[str, StateSnapshotEntry] = field(default_factory=dict)
    # Preloaded relief library bodies for mountain/road consumers (R33/R35)
    relief_templates_by_uid: dict[str, ReliefTemplate] = field(default_factory=dict)
    # Road paint → shoulder grade handoff for detailed later (R36u-T-10)
    painted_road_edges: list[PaintedRoadEdge] = field(default_factory=list)
    # §8c Grade entities (L0 outdoor ribbon removed — R36u-T-8; may stay empty)
    relief_grade_instances: list[ReliefGradeInstance] = field(default_factory=list)

    def require_surface_bundle(self) -> SurfacePlanBundle:
        if self.surface_bundle is None:
            raise ValueError("L0 compose requires a frozen surface plan bundle")
        if self.surface_bundle.world_uid != self.world.world_uid:
            raise ValueError("L0 surface plan belongs to another world")
        base = self.surface_bundle.relief.payload.light.base_surface_z
        if base and base[-1][0].tx + 1 != self.scale.side:
            raise ValueError("L0 scale differs from frozen surface plan")
        return self.surface_bundle
