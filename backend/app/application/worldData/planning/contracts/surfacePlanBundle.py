"""Immutable envelopes with exact cross-phase dependency coherence."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan, GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import StateViewRevision, WorldPlanScope
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.surfacePlanning.surfacePlanBindings import surface_plan_binding, geo_surface_plan_binding
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan, GeoWaterPlacementPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan, CoatingPlan
from app.dataModel.validation.immutableValue import validate_immutable


class SurfacePlanBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    view_revision: StateViewRevision = Field(min_length=32, max_length=32)
    world_uid: EntityUid
    climate_base: PlanEnvelope[ClimateBasePlan]
    terrain_base: PlanEnvelope[TerrainPlan]
    water_placement: PlanEnvelope[WaterPlacementPlan]
    relief: PlanEnvelope[ReliefPlan]
    hydrology_routes: PlanEnvelope[HydrologyRoutesPlan]
    river_relief: PlanEnvelope[RiverReliefPlan]
    hydrology: PlanEnvelope[HydrologyPlan]
    climate_local: PlanEnvelope[ClimateLocalPlan]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        S = SurfacePlanSlot
        envelopes = ((S.CLIMATE_BASE, self.climate_base), (S.TERRAIN_BASE, self.terrain_base),
            (S.WATER_PLACEMENT, self.water_placement), (S.RELIEF, self.relief),
            (S.HYDROLOGY_ROUTES, self.hydrology_routes), (S.RIVER_RELIEF, self.river_relief),
            (S.HYDROLOGY, self.hydrology), (S.CLIMATE_LOCAL, self.climate_local))
        refs = {slot.value: envelope.ref for slot, envelope in envelopes}
        for slot, envelope in envelopes:
            declaration = surface_plan_binding(slot)
            metadata = declaration.metadata
            key = envelope.ref.key
            if (key.world_uid != self.world_uid or key.scope != WorldPlanScope()
                    or key.contract_id != metadata.id
                    or key.schema_version != metadata.schema_version
                    or key.algorithm_version != metadata.algorithm_version):
                raise ValueError("surface bundle contains a foreign world/scope/phase/version")
            actual = {dep.slot: dep.ref for dep in envelope.dependencies}
            if actual != {dep.value: refs[dep.value] for dep in declaration.upstream}:
                raise ValueError("surface bundle contains incoherent dependency refs")
        return self


class GeoSurfacePlanBundle(BaseModel):
    """Exact GEO phases from one captured revision; no baseline envelope overrides."""

    model_config = SurfacePlanBundle.model_config

    view_revision: StateViewRevision = Field(min_length=32, max_length=32)
    world_uid: EntityUid
    climate_base: PlanEnvelope[ClimateBasePlan]
    terrain_base: PlanEnvelope[TerrainPlan]
    terrain_regions: PlanEnvelope[TerrainRegionPlan]
    water_placement: PlanEnvelope[GeoWaterPlacementPlan]
    relief: PlanEnvelope[ReliefPlan]
    hydrology_routes: PlanEnvelope[GeoHydrologyRoutesPlan]
    river_relief: PlanEnvelope[RiverReliefPlan]
    hydrology: PlanEnvelope[GeoHydrologyPlan]
    climate_local: PlanEnvelope[ClimateLocalPlan]
    coastline_boundaries: PlanEnvelope[CoastlineBoundaryPlan]
    surface_support: PlanEnvelope[SurfaceSupportPlan]
    coating: PlanEnvelope[CoatingPlan]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        validate_immutable(self)
        S = SurfacePlanSlot
        envelopes = ((S.CLIMATE_BASE, self.climate_base), (S.TERRAIN_BASE, self.terrain_base),
            (S.TERRAIN_REGIONS, self.terrain_regions), (S.WATER_PLACEMENT, self.water_placement),
            (S.RELIEF, self.relief), (S.HYDROLOGY_ROUTES, self.hydrology_routes),
            (S.RIVER_RELIEF, self.river_relief), (S.HYDROLOGY, self.hydrology),
            (S.CLIMATE_LOCAL, self.climate_local), (S.COASTLINE_BOUNDARIES, self.coastline_boundaries),
            (S.SURFACE_SUPPORT, self.surface_support), (S.COATING, self.coating))
        refs = {slot.value: envelope.ref for slot, envelope in envelopes}
        for slot, envelope in envelopes:
            declaration = geo_surface_plan_binding(slot)
            metadata, key = declaration.metadata, envelope.ref.key
            if (key.world_uid != self.world_uid or key.scope != WorldPlanScope()
                    or key.contract_id != metadata.id or key.schema_version != metadata.schema_version
                    or key.algorithm_version != metadata.algorithm_version):
                raise ValueError("GEO bundle contains a foreign world/scope/phase/version")
            actual = {dep.slot: dep.ref for dep in envelope.dependencies}
            if actual != {dep.value: refs[dep.value] for dep in declaration.upstream}:
                raise ValueError("GEO bundle contains incoherent dependency refs")
        if self.terrain_regions.payload.snapshot.world_uid != self.world_uid:
            raise ValueError("GEO region snapshot belongs to a foreign world")
        if (self.hydrology.payload.source_mapping != self.hydrology_routes.payload.source_mapping
                or self.hydrology.payload.classification_decisions != self.hydrology_routes.payload.classification_decisions):
            raise ValueError("GEO final hydrology must preserve route-stage mapping and decisions")
        for facts in self.surface_support.payload.facts:
            if (facts.world_uid != self.world_uid or facts.geometry_ref != self.river_relief.ref
                    or facts.support_input_fingerprint != self.surface_support.ref.key.input_fingerprint):
                raise ValueError("GEO support evidence is bound to a different input or river-relief revision")
        if any(outcome.identity.world_uid != self.world_uid for outcome in self.water_placement.payload.outcomes):
            raise ValueError("GEO placement outcomes belong to a foreign world")
        return self
