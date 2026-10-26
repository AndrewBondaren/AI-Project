"""Transit: hand ready bake-context inputs to the domain landcover composer.

The adapter holds no domain resolve of its own: topology/grid arrive resolved
on the context, domain observations live on ``working`` views, and the region
state ref is read once by the async owner upstream. Only the migration-only
surface channel below still touches world data, and it goes away in PC-11.7.
"""

from collections.abc import Mapping

from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.generators.terrain.landcover.types import (
    LandcoverInputs,
    StateSnapshotEntry,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.regions.inputs.landcoverInputs import (
    prepare_landcover_inputs as _compose_landcover_inputs,
    prepare_landcover_inputs_legacy,
)


def read_region_state_snapshot(ctx: LightGridBakeContext) -> Mapping[str, StateSnapshotEntry]:
    """The async bake/refine owner has already read the entity repository."""
    return ctx.region_state_snapshot


def prepare_landcover_inputs(ctx: LightGridBakeContext) -> LandcoverInputs:
    if ctx.working is not None:
        return _compose_landcover_inputs(
            ctx.working, read_region_state_snapshot(ctx))
    if ctx.surface_bundle is not None:
        raise ValueError("frozen landcover inputs require request working views")
    if ctx.topology is None or ctx.grid is None:
        raise ValueError("landcover inputs require topology/grid resolved by the operation owner")
    surface = ctx.surface_planning
    # Migration-only legacy channel until PC-11.7; profile resolution stays a
    # climate domain registry call, the adapter only forwards its result.
    profiles = ({str(anchor.system_climate_zone): profile_for(ctx.world, anchor.system_climate_zone)
                 for anchor in surface.local_field.anchors} if surface is not None else None)
    return prepare_landcover_inputs_legacy(
        ctx.topology, ctx.grid, surface, profiles, read_region_state_snapshot(ctx))
