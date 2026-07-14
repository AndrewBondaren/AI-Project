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
