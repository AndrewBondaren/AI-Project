"""G10-A exact GEO inputs, payloads and invariant phase envelopes."""

from typing import assert_type

from app.application.worldData.generators.terrain.hills.hillPlacement import place_hills
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def hills_with_explicit_exclusions(surface: dict[tuple[int, int], int], terrain: dict[tuple[int, int], str],
    excluded: frozenset[tuple[int, int]], registry: WorldTerrainRegistry) -> None:
    assert_type(place_hills(surface, terrain, excluded, terrain_registry=registry, seed=1, z_min=-10, z_max=20), None)

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


from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy, HydrologyGenerationBinding
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import CategoryWaterGenerationSettings, BodyWaterGenerationSettings
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.policy.policySpec import ValueSelectionPolicySpec
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason


def generation_policy_binding(inputs: GeoHydrologyPlanInput, category: CategoryWaterGenerationSettings,
    body: BodyWaterGenerationSettings) -> None:
    binding = bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation,
        defaults=inputs.defaults, category=category, body=body, root_path=(), context_path=())
    assert_type(binding, HydrologyGenerationBinding)
    assert_type(binding.context, WaterGenerationContext)
    assert_type(binding.spec, ValueSelectionPolicySpec[HydrologyExecutionMode, WaterPolicyReason])


from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord


def decision_driven_water_fill(owner: WaterBodyPlanner, inputs: GeoHydrologyPlanInput,
    placement: GeoWaterPlacementPlan, surface: tuple[tuple[SurfaceGridCoord, FineZ], ...],
    decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...], control: PlanBuildControl) -> None:
    assert_type(owner.plan_geo(world_uid="world", inputs=inputs, placement=placement,
        surface_z=surface, classification_decisions=decisions, control=control), PlanBuildResult[OpenWaterPlan])


from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan


def geo_route_assembly(owner: HydrologyRoutesAssembler, coarse: CoarseRiverPlanner, fine: FineRiverPlanner,
    inputs: GeoHydrologyPlanInput, relief: ReliefPlan, placement: GeoWaterPlacementPlan, water: OpenWaterPlan,
    decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...], control: PlanBuildControl) -> None:
    assert_type(owner.assemble_geo(world_uid="world", inputs=inputs, relief=relief, placement=placement,
        classification_decisions=decisions, control=control), PlanBuildResult[GeoHydrologyRoutesPlan])
    planned = coarse.plan(world_uid="world", inputs=inputs, surface_z=relief.surface_z, water=water, control=control)
    assert_type(planned, PlanBuildResult[CoarseRiverPlan])
    assert_type(fine.plan(world_uid="world", inputs=inputs, surface_z=relief.surface_z,
        water=water, coarse=planned.payload, control=control), PlanBuildResult[FineRiverPlan])



def captured_category_generation(view: GeoSurfacePlanningView) -> None:
    assert_type(view.water_placement.sea_generation, CategoryWaterGenerationSettings)
    assert_type(view.water_placement.ocean_generation, CategoryWaterGenerationSettings)
    assert_type(view.water_placement.lake_generation, CategoryWaterGenerationSettings)
    assert_type(view.hydrology.sea_generation, CategoryWaterGenerationSettings)
    assert_type(view.hydrology.ocean_generation, CategoryWaterGenerationSettings)
    assert_type(view.hydrology.lake_generation, CategoryWaterGenerationSettings)


from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyRoutesPlanProvider


def exact_geo_routes_provider(provider: GeoHydrologyRoutesPlanProvider, request: PlanRequest[GeoHydrologyPlanInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(provider.build(request, dependencies, control), PlanBuildResult[GeoHydrologyRoutesPlan])


from app.application.worldData.generators.terrain.regions.regionExtent import TerrainRegionPlanProvider
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput


def exact_region_provider(provider: TerrainRegionPlanProvider, request: PlanRequest[TerrainRegionPlanningInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(provider.build(request, dependencies, control), PlanBuildResult[TerrainRegionPlan])
    assert_type(request.inputs.snapshot_uid, EntityUid)
    assert_type(request.inputs.world_region_uid, EntityUid)


from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.terrain.designedWater.draft import WaterDesignDraft


def built_in_water_strategy_composition(value: WaterStrategyInput) -> None:
    factory = DesignedWaterStrategyFactory.builtins()
    assert_type(factory, DesignedWaterStrategyFactory)
    assert_type(factory.get(value.strategy).design(value), WaterDesignDraft)


from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import ProceduralWaterSourceAdapter
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.terrain.designedWater.input import WaterDesignInput
from app.dataModel.terrain.designedWater.fields.field import WaterFieldRecipe


def procedural_source_join(adapter: ProceduralWaterSourceAdapter, shared: WaterDesignInput[ProceduralSource],
    generation: HydrologyGenerationDecision, admission: PlacementAdmissionInput, recipe: WaterFieldRecipe, z_min: FineZ) -> None:
    result = adapter.prepare_source(shared, generation=generation, admission=admission, field_policy=recipe, z_min=z_min)
    assert_type(result.source, ProceduralSource)


from app.application.worldData.generators.terrain.designedWater.preparation.authoredWaterSourceAdapter import AuthoredWaterSourceAdapter
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput


def authored_source_join(adapter: AuthoredWaterSourceAdapter, shared: WaterDesignInput[AuthoredBasinSource],
    generation: HydrologyGenerationDecision, admission: PlacementAdmissionInput, geometry: AuthoredWaterGeometry) -> None:
    result = adapter.prepare_source(shared, generation=generation, admission=admission, geometry=geometry)
    assert_type(result, AuthoredWaterDesignInput[AuthoredBasinSource | AuthoredLakeSource])


from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.prepared import PreparedPlacementV2


def prepared_water_admission(owner: DesignedWaterPlacementPreparer, value: WaterStrategyInput,
    preparation: WaterDesignPreparation, intent: PlacementIntent, admission: PlacementAdmissionInput) -> None:
    assert_type(owner.bind_admission(value, preparation, intent=intent, admission=admission), PreparedPlacementV2)


from collections.abc import Callable
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.result import PlacementBatchResultV2


def common_placement_runner(session: PlacementSession, prepare: Callable[[tuple[PlacementHeader, ...]], None],
    check: Callable[[], None]) -> None:
    assert_type(session.run(prepare, check_cancelled=check), PlacementBatchResultV2)


from app.application.worldData.planning.composition.planProviders import GeoWorldPlanProviders
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.planning.service.planningService import PlanWaitControl


def captured_geo_assembly(assembler: SurfacePlanningAssembler[GeoWorldPlanProviders], view: GeoSurfacePlanningView,
    wait: PlanWaitControl) -> None:
    assert_type(assembler.prepare_geo(view, wait=wait), GeoSurfacePlanBundle | None)


from app.application.worldData.planning.composition.surfacePlanningAssembler import prepare_captured_geo_bundle
from app.application.jsonValidation.resolve import ResolveContext


def captured_geo_reporting(assembler: SurfacePlanningAssembler[GeoWorldPlanProviders], view: GeoSurfacePlanningView,
    wait: PlanWaitControl, ctx: ResolveContext) -> None:
    assert_type(prepare_captured_geo_bundle(view, planning=assembler, wait=wait, resolve_ctx=ctx), GeoSurfacePlanBundle | None)


from app.application.worldData.generators.terrain.landcover.planning.preWaterHillHosts import PreWaterHillHostPlanner
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.spatial.grid.coordinateTypes import FineXY


def pre_water_hill_hosts(world: EntityUid, inputs: SurfaceSupportInput, base: PlanEnvelope[ClimateBasePlan],
                         terrain: PlanEnvelope[TerrainPlan], cells: RegionCoverage) -> None:
    assert_type(PreWaterHillHostPlanner().prepare(world, inputs, base, terrain, cells=cells),
                tuple[tuple[FineXY, TerrainKey], ...])


from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput


def pre_carve_terrain(world: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                      inputs: SurfaceSupportInput, base: PlanEnvelope[ClimateBasePlan],
                      terrain: PlanEnvelope[TerrainPlan], cells: RegionCoverage, control: PlanBuildControl) -> None:
    assert_type(PreWaterTerrainPlanner().prepare(world, base_input, relief_input, inputs, base, terrain,
                cells=cells, control=control), tuple[SurfaceHeightmap, frozenset[tuple[int, int]]])


from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.dataModel.hydrology.planning.stages.openWaterPlan import AssembledWater, FineWaterResult
from app.dataModel.placement.result import PlacementBatchResultV2
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.topology.worldTopology import WorldTopology


def frozen_fine_water(world: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                      inputs: SurfaceSupportInput, base: PlanEnvelope[ClimateBasePlan],
                      terrain: PlanEnvelope[TerrainPlan], cells: RegionCoverage, control: PlanBuildControl,
                      window: PlanEnvelope[FineSurfaceWindow], expected: PlanRef, topology: WorldTopology,
                      specs: tuple[BasinSpec, ...], placement: PlanEnvelope[PlacementBatchResultV2], physical: GeoHydrologyPlanInput,
                      decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...]) -> None:
    assert_type(PreWaterTerrainPlanner().prepare_window(world, base_input, relief_input, inputs, base, terrain,
        cells=cells, control=control), PlanEnvelope[FineSurfaceWindow])
    assert_type(WaterBodyPlanner().fill_fine(window, expected_surface=expected, placement=placement,
        expected_placement=placement.ref, inputs=physical, specs=specs, classification_decisions=decisions, control=control),
        PlanEnvelope[FineWaterResult])
