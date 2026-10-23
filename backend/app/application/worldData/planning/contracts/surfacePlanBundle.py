"""Immutable envelopes with exact cross-phase dependency coherence."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import StateViewRevision, WorldPlanScope
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.surfacePlanning.surfacePlanBindings import surface_plan_binding
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan


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
