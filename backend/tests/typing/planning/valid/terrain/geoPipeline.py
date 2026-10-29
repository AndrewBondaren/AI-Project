"""G10-A exact GEO inputs, payloads and invariant phase envelopes."""

from typing import assert_type

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyFinalPlanProvider
from app.application.worldData.generators.hydrology.water.waterMaterialize import MaterializedWater
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import GeoReliefPlanProvider, GeoRiverReliefPlanProvider
from app.application.worldData.planning.composition.planProviders import declared_binding
from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import GeoSurfacePlanningView
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry, BoundaryGeometryResult
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.application.worldData.generators.hydrology.policy.hydrologyPolicyFacts import collect_hydrology_policy_facts
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer, PreparedCoastlineBoundary
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyPolicySnapshot, HydrologyPolicyFacts, HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput


def exact_geo_pipeline(view: GeoSurfacePlanningView, plans: GeoSurfacePlanBundle) -> None:
    assert_type(view.water_placement, GeoWaterPlacementInput)
    assert_type(view.hydrology, GeoHydrologyPlanInput)
    assert_type(plans.water_placement, PlanEnvelope[GeoWaterPlacementPlan])
    assert_type(plans.hydrology_routes, PlanEnvelope[GeoHydrologyRoutesPlan])
    assert_type(plans.hydrology, PlanEnvelope[GeoHydrologyPlan])
    assert_type(plans.terrain_regions, PlanEnvelope[TerrainRegionPlan])
    assert_type(plans.water_placement.payload.source_decisions, tuple[tuple[EntityUid, WaterDesignDecision], ...])
    assert_type(declared_binding(geo_surface_plan_binding(SurfacePlanSlot.WATER_PLACEMENT),
        GeoWaterPlacementInput, GeoWaterPlacementPlan), RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan])
    assert_type(declared_binding(geo_surface_plan_binding(SurfacePlanSlot.HYDROLOGY_ROUTES),
        GeoHydrologyPlanInput, GeoHydrologyRoutesPlan), RegisteredPlanContract[GeoHydrologyPlanInput, GeoHydrologyRoutesPlan])


def exact_geo_boundary(source: DeclaredCoastline, snapshot: BoundaryWaterSnapshot[GeoHydrologyPlan],
    policy: HydrologyPolicySnapshot[GeoHydrologyPlan], inputs: CoastlineBoundaryInput,
    admission: PlacementAdmissionInput, gates: HydrologyPlacementGateInputs,
    behavior: HydrologyPlacementBehaviorInputs, category: HydrologySeasPolicy) -> None:
    assert_type(snapshot.hydrology, PlanEnvelope[GeoHydrologyPlan])
    assert_type(policy.hydrology, PlanEnvelope[GeoHydrologyPlan] | None)
    assert_type(collect_hydrology_policy_facts(source, policy), HydrologyPolicyFacts)
    bind_hydrology_placement_policy(source, category, gates, behavior, policy, source_path=(), category_path=())
    assert_type(BoundaryGeometry().prepare(source, snapshot), BoundaryGeometryResult)
    assert_type(AttachedCoastlinePreparer().prepare_boundary(source, snapshot, admission), PreparedCoastlineBoundary)
    assert_type(CoastlineBoundaryPlanner().prepare(inputs, snapshot, (admission,),
        snapshot_uid=snapshot.hydrology.ref.key.world_uid), CoastlineBoundaryPlan)


def exact_geo_final_provider(provider: GeoHydrologyFinalPlanProvider, request: PlanRequest[HydrologyFinalInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(provider.build(request, dependencies, control), PlanBuildResult[GeoHydrologyPlan])


def exact_geo_relief_providers(relief: GeoReliefPlanProvider, river: GeoRiverReliefPlanProvider,
    request: PlanRequest[ReliefPlanInput], river_request: PlanRequest[RiverReliefInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(relief.build(request, dependencies, control), PlanBuildResult[ReliefPlan])
    assert_type(river.build(river_request, dependencies, control), PlanBuildResult[RiverReliefPlan])


def final_materialized_source_mapping(result: MaterializedWater) -> None:
    assert_type(result.source_mapping, SourceBodyMapping)


def route_stage_sources(view: GeoSurfacePlanningView, water: OpenWaterPlan) -> None:
    assert_type(view.hydrology.generation, WorldWaterGenerationSettings)
    assert_type(view.hydrology.defaults, WaterGenerationDefaults)
    assert_type(water.source_mapping, SourceBodyMapping)
