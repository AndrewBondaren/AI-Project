"""Positive surface providers contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.planning.providers.planProvider import PlanProvider
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.climate.localFieldFromCoarse import build_local_plan_from_coarse
from app.application.worldData.generators.climate.planning.climatePlanProvider import (
    ClimateBasePlanProvider,
    ClimateLocalPlanProvider,
)
from app.application.worldData.generators.terrain.planning.terrainPlanProvider import TerrainPlanProvider
from app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider import WaterPlacementPlanProvider
from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import (
    ReliefPlanProvider,
    RiverReliefPlanProvider,
)
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverBedRecord, RiverReliefPlan


def climate_base_provider_type(provider: ClimateBasePlanProvider) -> PlanProvider[ClimateBaseInput, ClimateBasePlan]:
    return provider


def terrain_base_provider_type(provider: TerrainPlanProvider) -> PlanProvider[TerrainBaseInput, TerrainPlan]:
    return provider


def surface_slot_boundary(member: SurfacePlanSlot) -> PlanSlot:
    slot = PlanSlot(member.value)
    assert_type(slot, PlanSlot)
    return slot


def water_placement_provider_type(provider: WaterPlacementPlanProvider) -> PlanProvider[WaterPlacementInput, WaterPlacementPlan]:
    return provider


def relief_provider_type(provider: ReliefPlanProvider) -> PlanProvider[ReliefPlanInput, ReliefPlan]:
    return provider


def river_relief_provider_type(provider: RiverReliefPlanProvider) -> PlanProvider[RiverReliefInput, RiverReliefPlan]:
    return provider


def climate_domain_round_trip(request: PlanRequest[ClimateBaseInput],
                              lookup: CacheLookup[PlanEnvelope[ClimateBasePlan]]) -> int | None:
    assert_type(request.inputs, ClimateBaseInput)
    if isinstance(lookup, CacheHit):
        assert_type(lookup.entry.value.payload, ClimateBasePlan)
        return lookup.entry.value.payload.profiles[0].values.base_temperature
    return None


def terrain_domain_round_trip(request: PlanRequest[TerrainBaseInput],
                              entry: CacheEntry[PlanEnvelope[TerrainPlan]]) -> TerrainPlan:
    assert_type(request.inputs, TerrainBaseInput)
    assert_type(entry.value.payload, TerrainPlan)
    return entry.value.payload


def relief_domain(entry: CacheEntry[PlanEnvelope[ReliefPlan]],
                  bed: RiverBedRecord[SurfaceGridCoord]) -> ReliefPlan:
    assert_type(bed.bed_z[0][0], SurfaceGridCoord)
    assert_type(entry.value.payload, ReliefPlan)
    return entry.value.payload


def valid_local_provider(provider: ClimateLocalPlanProvider, request: PlanRequest[ClimateLocalInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[ClimateLocalPlan]:
    return provider.build(request, dependencies, control)


def valid_local_adapter(inputs: ClimateLocalInput, base: ClimateBasePlan,
    hydrology: HydrologyPlan) -> PlanBuildResult[ClimateLocalPlan]:
    return build_local_plan_from_coarse(inputs, base, hydrology)
