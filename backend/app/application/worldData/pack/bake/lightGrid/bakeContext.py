"""Caller contract for L0 light compose — tz_map_light_bake."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import (
    RibbonIntent,
)
from app.application.worldData.pack.bake.lightGrid.paintedRoadEdge import PaintedRoadEdge
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
    surface_planning: SurfaceTerrainContext | None = None
    pole_field: ClimatePoleField | None = None
    terrain_system_keys: set[str] = field(default_factory=set)
    # Preloaded relief library bodies for mountain/road consumers (R33/R35)
    relief_templates_by_uid: dict[str, ReliefTemplate] = field(default_factory=dict)
    # Road paint → shoulder grade handoff (RELIEF-T-31)
    painted_road_edges: list[PaintedRoadEdge] = field(default_factory=list)
    # Ribbon grade intents (road_shoulder / open_land / shore) → BAR-1 after compose
    ribbon_intents: list[RibbonIntent] = field(default_factory=list)
    # §8c Grade entities created during shoulder/volume stamp
    relief_grade_instances: list[ReliefGradeInstance] = field(default_factory=list)
