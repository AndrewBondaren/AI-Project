"""Pre-water landcover hosts from captured base facts, before basin carving."""

from dataclasses import replace
from collections.abc import Iterable

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.application.worldData.generators.terrain.landcover.planning.capturedSources import (
    CapturedLandcoverSources, capture_landcover_policy,
)
from app.application.worldData.generators.terrain.landcover.types import LandcoverInputs, StateSnapshotEntry
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.application.worldData.regions.factConsumers import collect_facts
from app.application.worldData.regions.factConsumers.climate import contribute_base
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import RegionFacts
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineXY, GridX, GridY
from app.dataModel.spatial.regionShape import Point
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PreWaterHillHostJob:
    """Landcover base observations and scoped projection; no water/materialization work."""

    def __init__(self, world_uid: EntityUid, inputs: SurfaceSupportInput,
                 climate_base: PlanEnvelope[ClimateBasePlan], terrain_base: PlanEnvelope[TerrainPlan]):
        if any(e.ref.key.world_uid != world_uid for e in (climate_base, terrain_base)) or (
                climate_base.ref.key.scope != terrain_base.ref.key.scope):
            raise ValueError("pre-water hosts require same-world/scope base envelopes")
        if not any(d.slot == SurfacePlanSlot.CLIMATE_BASE and d.ref == climate_base.ref
                   for d in terrain_base.dependencies):
            raise ValueError("terrain base must bind the supplied climate base revision")
        bounds, bbox = inputs.topology.bounds, terrain_base.payload.bbox
        if (bounds.x_min, bounds.y_min, bounds.x_max, bounds.y_max) != (
                bbox.x_min, bbox.y_min, bbox.x_max, bbox.y_max):
            raise ValueError("terrain base extent must match captured topology")
        self.inputs, self.base = inputs, climate_base.payload
        self.profiles = {p.key: ClimateZoneProfile.from_data(p.key, p.values) for p in self.base.profiles}
        self.context = FactConsumerContext(cells=(), terrain=TerrainWorkingFields.from_plan(terrain_base.payload))
        registry, policy = capture_landcover_policy(inputs)
        observations = LandcoverInputs(inputs.topology, self.facts_at, {
            s.region_uid: StateSnapshotEntry(s.current_type, s.tombstone, s.spec_fingerprint)
            for s in inputs.region_states})
        self.sources = CapturedLandcoverSources(world_uid, inputs, observations, registry, policy, self.profile_at)

    def profile_at(self, gx: GridX, gy: GridY) -> ClimateZoneProfile:
        sample = ClimatePlanSampler.sample_prepared(self.base, self.profiles, gx, gy)
        return self.profiles[sample.system_climate_zone]

    def facts_at(self, point: Point) -> RegionFacts:
        macro = (point[0] // self.inputs.grid.fine_span, point[1] // self.inputs.grid.fine_span)
        context = replace(self.context, cells=(macro,))
        return replace(collect_facts(context), climate=contribute_base(self.base, self.profiles, context.cells))

    def project(self, cells: RegionCoverage) -> tuple[tuple[FineXY, TerrainKey], ...]:
        bounds = fine_topology(self.inputs.topology, self.inputs.grid.fine_span).bounds
        for span in cells.spans:
            if not bounds.contains(span.x0, span.y) or not bounds.contains(span.x1 - 1, span.y):
                raise ValueError("pre-water coverage must use canonical fine cells within captured topology")
        return self._project((FineX(x), span.y) for span in cells.spans for x in range(span.x0, span.x1))

    def project_tile(self, gx: int, gy: int) -> tuple[tuple[FineXY, TerrainKey], ...]:
        if self.inputs.topology.canonicalize(gx, gy) != (gx, gy):
            raise ValueError("hill host tile must be canonical")
        span = self.inputs.grid.fine_span
        return self._project((FineX(x), FineY(y)) for y in range(gy*span, (gy+1)*span)
                             for x in range(gx*span, (gx+1)*span))

    def _project(self, cells: Iterable[FineXY]) -> tuple[tuple[FineXY, TerrainKey], ...]:
        if not self.inputs.masks_enabled or not self.sources.policy.enabled:
            return ()
        result: list[tuple[FineXY, TerrainKey]] = []
        for cell in cells:
            terrain = self.sources.terrain_at(cell)
            if terrain is None:
                raise PlanBuildFailure((FieldPathError(("pre_water_hill_hosts", *cell),
                    "landcover host is unresolved from the supplied base facts"),))
            result.append((cell, terrain))
        return tuple(result)


class PreWaterHillHostPlanner:
    """Public operation; landcover implementation stays in its domain job."""

    def prepare(self, world_uid: EntityUid, inputs: SurfaceSupportInput,
                climate_base: PlanEnvelope[ClimateBasePlan], terrain_base: PlanEnvelope[TerrainPlan], *,
                cells: RegionCoverage) -> tuple[tuple[FineXY, TerrainKey], ...]:
        return PreWaterHillHostJob(world_uid, inputs, climate_base, terrain_base).project(cells)
