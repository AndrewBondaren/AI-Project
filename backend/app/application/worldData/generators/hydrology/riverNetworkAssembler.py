"""Plan rivers atomically, apply relief once, then publish roles and diagnostics."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldRow import hydrology
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import autoresolve_river_segments
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import resolve_river_type_classify
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles
from app.application.worldData.generators.hydrology.rivers.riverPrepare import PreparedRiver, prepare_river
from app.application.worldData.generators.hydrology.rivers.riverRouteDiagnostics import emit_river_diagnostic
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import (
    RiverRouteRequest, declared_river_requests, request_from_segments,
)
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput, RiverSegment
from app.application.worldData.generators.hydrology.waterfalls.riverDrops import river_drop_facts
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec, apply_river_bed_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.waterfallDrop import WaterfallDrop
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class AssembledRivers:
    by_cell: dict[Coord, MapCellHydrology]
    segments: list[RiverSegment]
    dirty_bbox: GridBBox | None
    drops: tuple[WaterfallDrop, ...]
    diagnostics: tuple[RiverRouteDiagnostic, ...]


def _prepare_requests(world: World, heightmap: SurfaceHeightmap, requests: Sequence[RiverRouteRequest],
                      claims: dict[Coord, MapCellHydrology], topology: WorldTopology,
                      policy: HydrologyRiversPolicy, water_bodies: Sequence[WaterBody],
                      ctx: ResolveContext, z_min: int) -> list[PreparedRiver]:
    jobs = []
    for request in requests:
        job = prepare_river(world, heightmap, request, claims, topology, policy, water_bodies, ctx, z_min)
        jobs.append(job)
        # Reservations only. Materialized roles are published after relief apply.
        for spec in job.specs:
            for cell, _ in spec.bed_z:
                claims[cell] = MapCellHydrology(role=HydrologyCellRole.RIVER_BED)
    return jobs


def assemble_rivers(world: World, heightmap: SurfaceHeightmap, master: HydrologyMasterInput,
                     occupied: dict[Coord, MapCellHydrology] | None = None,
                     locations: Sequence[NamedLocation] | None = None, *, topology: WorldTopology,
                     water_bodies: Sequence[WaterBody] = (), ctx: ResolveContext | None = None) -> AssembledRivers:
    """Return accepted materialized segments only; independent failures are explicit.

    All profiles use one pre-bed snapshot. Shared receiving mouths are allowed;
    occupied interior beds are reserved between objects. Runtime alone can reroute.
    """
    if not isinstance(topology, WorldTopology):
        raise TypeError("river assembly requires an explicit WorldTopology")
    ctx = ctx if ctx is not None else ResolveContext()
    occupied = dict(occupied or {})
    claims = dict(occupied)
    policy = hydrology(world).default_rivers
    type_classify = resolve_river_type_classify(world)
    z_min = world_z_min(world)
    requests = declared_river_requests(world, heightmap, master, locations or (), occupied, type_classify, topology)
    jobs = _prepare_requests(world, heightmap, requests, claims, topology, policy, water_bodies, ctx, z_min)
    if policy.enabled and policy.autoresolve:
        auto = autoresolve_river_segments(world, heightmap, master, claims, topology=topology)
        requests = [request_from_segments(world, (segment,), occupied, space=CoordinateSpace.WORLD_SURFACE_GRID)
                    for segment in auto]
        jobs.extend(_prepare_requests(world, heightmap, requests, claims, topology, policy, water_bodies, ctx, z_min))
    apply_river_bed_z(heightmap, tuple(spec for job in jobs for spec in job.specs))
    merged, segments, drops = {}, [], []
    for job in jobs:
        for segment, spec in zip(job.segments, job.specs, strict=True):
            merged.update(river_bed_roles(segment, spec))
            segments.append(segment)
            actual = RiverBedSpec(tuple((cell, heightmap.surface_z[cell]) for cell, _ in spec.bed_z))
            drops.extend(river_drop_facts(heightmap, segment, actual, occupied))
    diagnostics = tuple(fact for job in jobs for fact in job.diagnostics)
    for diagnostic in diagnostics:
        emit_river_diagnostic(ctx, diagnostic)
    dirty = None
    if merged:
        xs, ys = zip(*merged)
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return AssembledRivers(merged, segments, dirty, tuple(drops), diagnostics)
