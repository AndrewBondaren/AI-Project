"""Resolve the sea carvers' topology on the coarse heightmap grid."""

from typing import overload

from app.application.jsonValidation.worldRow import terrain_scalars
from app.application.worldData.generators.terrain.passes.bbox import world_bounds_from_world
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@overload
def resolve_hydrology_topology(world: World, heightmap: SurfaceHeightmap, *,
                               locations: list[NamedLocation] | None = None) -> WorldTopology: ...


@overload
def resolve_hydrology_topology(world: World, heightmap: None = None, *,
                               locations: list[NamedLocation] | None = None) -> WorldTopology | None: ...


def resolve_hydrology_topology(world: World, heightmap: SurfaceHeightmap | None = None, *,
                               locations: list[NamedLocation] | None = None) -> WorldTopology | None:
    bounds = world_bounds_from_world(world, locations)
    if bounds is None and heightmap is not None:
        # Legacy worlds have no declared extent; their resolved surface is the world.
        bbox = heightmap.bbox
        bounds = WorldBounds(x_min=bbox.x_min, x_max=bbox.x_max,
                             y_min=bbox.y_min, y_max=bbox.y_max)
    if bounds is None:
        return None
    return WorldTopology(mode=terrain_scalars(world).world_topology_mode, bounds=bounds)
