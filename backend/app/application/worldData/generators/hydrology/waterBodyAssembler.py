"""Post-1.4 water orchestration: components → levels → fill/classify → shore."""

from collections.abc import Callable, Sequence

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.water.planning.waterAssemblyResult import AssembledWater, finalize_water, unresolved_water
from app.application.worldData.generators.hydrology.water.depressionTree import depression_tree
from app.application.worldData.generators.hydrology.water.waterBodyResolver import resolve_water_levels
from app.application.worldData.generators.hydrology.water.waterMaterialize import materialize_water
from app.application.worldData.generators.hydrology.water.waterSources import water_sources
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic


def assemble_water_bodies(heightmap: SurfaceHeightmap, specs: Sequence[BasinSpec],
                          topology: WorldTopology, policy: WorldHydrology, *,
                          change_uid: str, auto_seas: bool, auto_lakes: bool,
                          ctx: ResolveContext | None = None,
                          allowed_kinds: frozenset[BasinKind] | None = None,
                          emit: Callable[[PlanDiagnostic], None] | None = None) -> AssembledWater:
    ctx = ctx or ResolveContext()
    if not change_uid:
        raise ValueError("water resolution requires a nonempty operation UID")
    try:
        tree = depression_tree(heightmap.surface_z, topology)
    except ValueError as error:
        return unresolved_water(heightmap.world_uid, error, ctx, emit)
    sources = water_sources(heightmap.surface_z, specs, tree, topology, policy,
                             auto_seas=auto_seas, auto_lakes=auto_lakes)
    resolved = resolve_water_levels(tree, sources, world_uid=heightmap.world_uid,
                                     change_uid=change_uid,
                                     default_water_level=policy.default_water_level)
    water = materialize_water(heightmap.surface_z, sources, resolved, topology, policy, ctx, allowed_kinds, emit=emit)
    return finalize_water(water, resolved, sources, world_uid=heightmap.world_uid, change_uid=change_uid,
                          topology=topology, policy=policy, auto_seas=auto_seas, ctx=ctx, emit=emit)
