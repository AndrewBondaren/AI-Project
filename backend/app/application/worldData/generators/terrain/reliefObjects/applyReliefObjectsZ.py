"""Pass 1.4 facade — mountain rise + ravine drop on coarse ``SurfaceHeightmap``.

Mutates ``heightmap.surface_z`` in place (frozen dataclass shell ≠ immutable map).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import apply_basin_z
from app.application.worldData.generators.terrain.reliefObjects.mountainZ import apply_mountain_z
from app.application.worldData.generators.terrain.reliefObjects.ravineZ import apply_ravine_z
from app.dataModel.worldPack.wire.worldMapCellsPerTile import resolve_world_map_side

if TYPE_CHECKING:
    from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
    from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
    from app.application.worldData.generators.terrain.types import SurfaceHeightmap
    from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
    from app.dataModel.topology.worldTopology import WorldTopology
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.world import World


def apply_relief_objects_z(
    world: World,
    locations: list[NamedLocation],
    heightmap: SurfaceHeightmap,
    *,
    pole_field: ClimatePoleField | None = None,
    light_side: int | None = None,
    basin_specs: Sequence[BasinSpec] = (),
    topology: WorldTopology | None = None,
    grid: SurfaceGridSettings | None = None,
) -> SurfaceHeightmap:
    """
    Mutate ``heightmap.surface_z`` in place (mountain rise, then ravine drop).
    Does not write hydrology roles — Pass 1.5 owns that.

    ``pole_field`` required for mountain autoresolve; if omitted, resolved via pole pass.
    ``light_side`` — WP-10 mask side for declare→macro radius; default from policy constant.
    """
    pole = pole_field if pole_field is not None else run_pole_resolve_pass(world, locations)
    side = int(light_side) if light_side is not None else resolve_world_map_side()
    raised = apply_mountain_z(
        world, locations, heightmap, pole_field=pole, light_side=side,
    )
    apply_ravine_z(world, heightmap)
    if basin_specs:
        if topology is None:
            raise ValueError("basin_specs require world topology")
        apply_basin_z(heightmap, basin_specs, topology, reserved=raised, grid=grid)
    return heightmap
