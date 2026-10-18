"""Prepare world-scoped facts and a state read boundary for LANDCOVER."""

from collections.abc import Mapping

from app.application.jsonValidation import terrain_scalars
from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.generators.terrain.landcover.types import LandcoverInputs, StateSnapshotEntry
from app.application.worldData.generators.terrain.passes.bbox import world_bounds_from_world
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.regions.factConsumers import collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.dataModel.worldPack.wire.worldTopology import WorldTopology


def read_region_state_snapshot(ctx: LightGridBakeContext) -> Mapping[str, StateSnapshotEntry]:
    """The async bake/refine owner has already read the entity repository."""
    return ctx.region_state_snapshot


def prepare_landcover_inputs(ctx: LightGridBakeContext) -> LandcoverInputs:
    bounds = world_bounds_from_world(ctx.world, ctx.locations)
    if bounds is None:
        raise ValueError("LANDCOVER requires world bounds independent of bake scope")
    topology = WorldTopology(mode=terrain_scalars(ctx.world).world_topology_mode, bounds=bounds)
    surface = ctx.surface_planning
    profiles = ({anchor.system_climate_zone: profile_for(ctx.world, anchor.system_climate_zone)
                 for anchor in surface.local_field.anchors} if surface is not None else None)

    def facts_at(point):
        # Region coordinates are fine cells; fact consumers observe macro cells.
        macro = (point[0] // ctx.scale.tile_m, point[1] // ctx.scale.tile_m)
        return collect_facts(FactConsumerContext(surface, (macro,), profiles))

    return LandcoverInputs(topology, facts_at, read_region_state_snapshot(ctx))
