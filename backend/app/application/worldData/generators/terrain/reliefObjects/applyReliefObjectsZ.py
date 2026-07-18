"""Pass 1.4 facade — mountain rise + ravine drop on coarse ``SurfaceHeightmap``.

Mutates ``heightmap.surface_z`` in place (frozen dataclass shell ≠ immutable map).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.reliefObjects.mountainZ import apply_mountain_z
from app.application.worldData.generators.terrain.reliefObjects.ravineZ import apply_ravine_z
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_side

if TYPE_CHECKING:
    from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
    from app.application.worldData.generators.terrain.types import SurfaceHeightmap
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.world import World


def apply_relief_objects_z(
    world: World,
    locations: list[NamedLocation],
    heightmap: SurfaceHeightmap,
    *,
    pole_field: ClimatePoleField | None = None,
    light_side: int | None = None,
) -> SurfaceHeightmap:
    """
    Mutate ``heightmap.surface_z`` in place (mountain rise, then ravine drop).
    Does not write hydrology roles — Pass 1.5 owns that.

    ``pole_field`` required for mountain autoresolve; if omitted, resolved via pole pass.
    ``light_side`` — WP-10 mask side for declare→macro radius; default from policy constant.
    """
    pole = pole_field if pole_field is not None else run_pole_resolve_pass(world, locations)
    side = int(light_side) if light_side is not None else resolve_world_map_side()
    apply_mountain_z(
        world, locations, heightmap, pole_field=pole, light_side=side,
    )
    apply_ravine_z(world, heightmap)
    return heightmap
