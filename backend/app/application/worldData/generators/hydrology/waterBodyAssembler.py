"""Post-1.4 water orchestration: components → levels → fill/classify → shore."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.water.depressionTree import depression_tree
from app.application.worldData.generators.hydrology.water.waterBodyResolver import resolve_water_levels
from app.application.worldData.generators.hydrology.water.waterDiagnostics import water_issue
from app.application.worldData.generators.hydrology.water.waterMaterialize import MaterializedWater, materialize_water
from app.application.worldData.generators.hydrology.water.waterSources import water_sources
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.enums.waterSystemKind import WaterSystemKind
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.ids.waterSystemIdentity import water_system_uid


@dataclass(frozen=True)
class AssembledWater:
    materialized: MaterializedWater
    physical_unions: tuple[PhysicalWaterUnion, ...]


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
        water_issue(ctx, heightmap.world_uid, str(error), "WATER_TERRAIN_UNRESOLVED",
                    disposition=PlanDiagnosticDisposition.ERROR, emit=emit)
        return AssembledWater(MaterializedWater({}, (), {}, {}, {}, SourceBodyMapping(entries=())), ())
    sources = water_sources(heightmap.surface_z, specs, tree, topology, policy,
                             auto_seas=auto_seas, auto_lakes=auto_lakes)
    resolved = resolve_water_levels(tree, sources, world_uid=heightmap.world_uid,
                                     change_uid=change_uid,
                                     default_water_level=policy.default_water_level)
    water = materialize_water(heightmap.surface_z, sources, resolved, topology, policy, ctx, allowed_kinds, emit=emit)
    # Procedural minima of one connected water are one positional body.
    normalized = {}
    aliases = {}
    body_uids = {body.water_body_uid for body in water.bodies}
    raw = {union.water_system_uid: union for union in resolved.unions}
    for union in resolved.unions:
        members = tuple(sorted({water.uid_remap.get(uid, uid) for uid in union.member_uids}))
        if len(members) > 1 and all(uid in body_uids for uid in members):
            uid = water_system_uid(heightmap.world_uid, change_uid, members, WaterSystemKind.PHYSICAL_MERGE)
            aliases[union.water_system_uid] = uid
            normalized[uid] = union.with_identity(uid, members)

    children = {uid: set() for uid in normalized}
    for old_uid, uid in aliases.items():
        previous = raw[old_uid].parent_system_uid
        while previous is not None and (previous not in aliases or aliases[previous] == uid):
            previous = raw[previous].parent_system_uid
        parent = aliases[previous] if previous is not None else None
        normalized[uid] = normalized[uid].with_parent_system(parent)
        if parent is not None:
            children[parent].add(uid)
    unions = tuple(union.with_child_systems(tuple(sorted(children[uid])))
                   for uid, union in normalized.items())
    nearest = {}
    for union in unions:
        for member in union.member_uids:
            candidate = (len(union.member_uids), union.water_system_uid)
            nearest[member] = min(nearest.get(member, candidate), candidate)
    water = replace(water, bodies=tuple(body.with_parent_system(
        nearest[body.water_body_uid][1] if body.water_body_uid in nearest else None,
    ) for body in water.bodies))
    if auto_seas and not any(source.spec.z_water_level == policy.default_water_level for source in sources):
        water_issue(ctx, heightmap.world_uid, "natural-only autoresolve: no ocean depression",
                    "WATER_NO_OCEAN_DEPRESSION", disposition=PlanDiagnosticDisposition.ERROR, emit=emit)
    if (sum(water.areas.values()) * 2 >= topology.bounds.width * topology.bounds.height
            and any(body.kind is not BasinKind.LAKE for body in water.bodies)):
        water_issue(ctx, heightmap.world_uid, "world is ocean: water covers at least half the world",
                    "WATER_WORLD_OCEAN", disposition=PlanDiagnosticDisposition.NOTICE, emit=emit)
    return AssembledWater(water, unions)
