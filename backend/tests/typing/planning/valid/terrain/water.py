"""Positive terrain water contracts; checked statically by Pyright."""

from typing import assert_type

from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource, WaterDesignSourceKind
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
from app.dataModel.terrain.designedWater.fields.field import (
    ContinentalField,
    NoiseRecipe,
    PlateNoiseRecipe,
    PlateRecipe,
)
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import BasinFloorProfile, FieldFloorProfile, FloorProfileKind
from app.dataModel.topology.worldTopology import Coord
from app.application.worldData.generators.terrain.designedWater.strategies.strategy import DesignedWaterStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.terrain.designedWater.input import (
    WaterStrategyInput, AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput,
)
from app.dataModel.terrain.designedWater.draft import (
    WaterDesignDraft, WaterDesignDraftKind, AuthoredWaterDesignDraft, ProceduralWaterDesignDraft,
)
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, FineArea, WaterCoverageBudget
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.placement.prepared import PlacementCandidate
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry, AuthoredWaterGeometryRequest
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.generators.terrain.designedWater.strategies.authoredRegionStrategy import AuthoredRegionStrategy
from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_water_source
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.identity.uid import EntityUid


def valid_water_contracts(source: WaterDesignSource, metadata: WaterSourceMetadata,
                          field: ContinentalField, profile: BasinFloorProfile) -> None:
    if source.kind is WaterDesignSourceKind.PROCEDURAL:
        assert_type(source.value, ProceduralWaterSource)
    if field.recipe.strategy is Strategy.CONTINENTAL_NOISE:
        assert_type(field.recipe, NoiseRecipe)
    elif field.recipe.strategy is Strategy.PLATE:
        assert_type(field.recipe, PlateRecipe)
    else:
        assert_type(field.recipe, PlateNoiseRecipe)
    assert_type(field.samples[0][0], SurfaceGridCoord)
    assert_type(field.samples[0][1], float)
    assert_type(metadata.level, FineZ)
    if profile.kind is FloorProfileKind.FIELD:
        assert_type(profile, FieldFloorProfile)
        assert_type(profile.z_min, FineZ)
    else:
        assert_type(profile.samples[0][0], Coord)


def valid_strategy_boundary(input: WaterStrategyInput, draft: WaterDesignDraft,
                            implementation: DesignedWaterStrategy) -> None:
    assert_type(input.context, ResolvedWaterGenerationContext)
    assert_type(input.budget, BodyCoverageAllocation)
    if input.strategy is Strategy.AUTHORED_REGION:
        assert_type(input, AuthoredWaterDesignInput)
    elif input.strategy is Strategy.CONTINENTAL_NOISE:
        assert_type(input, NoiseWaterDesignInput)
        assert_type(input.field_policy, NoiseRecipe)
    elif input.strategy is Strategy.PLATE:
        assert_type(input, PlateWaterDesignInput)
        assert_type(input.field_policy, PlateRecipe)
    else:
        assert_type(input, PlateNoiseWaterDesignInput)
        assert_type(input.field_policy, PlateNoiseRecipe)
    if draft.kind is WaterDesignDraftKind.AUTHORED:
        assert_type(draft, AuthoredWaterDesignDraft)
    else:
        assert_type(draft, ProceduralWaterDesignDraft)
    factory = DesignedWaterStrategyFactory(authored_region=implementation,
        continental_noise=implementation, plate=implementation, plate_noise=implementation)
    assert_type(factory.get(input.strategy), DesignedWaterStrategy)
    assert_type(factory.get(input.strategy).design(input), WaterDesignDraft)
    assert_type(input.validate_draft(draft), WaterDesignDraft)


def valid_budget_boundary(policy: WaterCoverageBudgetPolicy, extent: TerrainRegionExtent,
                          context: ResolvedWaterGenerationContext,
                          requests: tuple[BodyCoverageRequest, ...],
                          authored: FineArea, available: FineArea) -> WaterCoverageBudget:
    budget = policy.calculate(extent, context, requests,
        authored_union_fine2=authored, available_auto_area_fine2=available)
    assert_type(budget, WaterCoverageBudget)
    assert_type(budget.allocations, tuple[BodyCoverageAllocation, ...])
    return budget


def valid_geometry_boundary(preparer: DesignedWaterPlacementPreparer, input: WaterStrategyInput,
                            draft: WaterDesignDraft, selection: WaterFieldSelectionPolicy) -> WaterDesignPreparation:
    result = preparer.prepare(input, draft, selection_policy=selection)
    assert_type(result, WaterDesignPreparation)
    assert_type(result.candidates, tuple[PlacementCandidate, ...])
    assert_type(result.metadata, WaterSourceMetadata)
    assert_type(result.floor_profile, BasinFloorProfile | None)
    return result


def valid_authored_boundary(request: AuthoredWaterGeometryRequest, input: AuthoredWaterDesignInput,
                            basin: DeclaredBasin) -> AuthoredWaterDesignDraft:
    assert_type(prepare_authored_water_geometry(request), AuthoredWaterGeometry)
    assert_type(input.geometry, AuthoredWaterGeometry)
    assert_type(project_water_source(basin, 2), DeclaredBasin)
    implementation: DesignedWaterStrategy = AuthoredRegionStrategy()
    assert_type(implementation.design(input), AuthoredWaterDesignDraft)
    return AuthoredRegionStrategy().design(input)


def valid_coastline_purpose(value: DeclaredCoastline) -> None:
    assert_type(value.purpose, CoastlinePurpose)
    assert_type(value.target_source_uid, EntityUid | None)
    assert_type(value.is_water_source, bool)


from app.dataModel.terrain.designedWater.input import WaterDesignInput
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource, ProceduralSource, AuthoredBasinSource


def valid_generic_sources(coast: NoiseWaterDesignInput[CoastlineWaterSource],
                          procedural: NoiseWaterDesignInput[ProceduralSource],
                          plate: PlateWaterDesignInput[CoastlineWaterSource],
                          mixed: PlateNoiseWaterDesignInput[CoastlineWaterSource],
                          authored: AuthoredWaterDesignInput[AuthoredBasinSource],
                          implementation: DesignedWaterStrategy) -> None:
    assert_type(coast.source, CoastlineWaterSource)
    assert_type(procedural.source, ProceduralSource)
    assert_type(plate.source, CoastlineWaterSource)
    assert_type(mixed.source, CoastlineWaterSource)
    assert_type(authored.source, AuthoredBasinSource)
    common: WaterDesignInput[CoastlineWaterSource] = coast
    assert_type(common.source, CoastlineWaterSource)
    accepted: WaterStrategyInput = coast
    assert_type(implementation.design(accepted), WaterDesignDraft)
    assert_type(implementation.design(procedural), WaterDesignDraft)
    assert_type(implementation.design(plate), WaterDesignDraft)
    assert_type(implementation.design(mixed), WaterDesignDraft)
    assert_type(implementation.design(authored), WaterDesignDraft)


from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import WaterDesignConstraints
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer import CoastlineConstraintPreparer


def valid_coastline_constraints(request: AuthoredWaterGeometryRequest,
                               input: NoiseWaterDesignInput[CoastlineWaterSource]) -> None:
    captured = CoastlineConstraintPreparer().prepare(request)
    assert_type(captured, WaterDesignConstraints)
    assert_type(captured.allowed_cells, frozenset[Coord])
    assert_type(captured.required_cells, frozenset[Coord])
    assert_type(input.constraints, WaterDesignConstraints | None)


from app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter import CoastlineWaterSourceAdapter
from app.dataModel.terrain.designedWater.input import CoastlineWaterDesignInput
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.terrain.designedWater.fields.field import WaterFieldRecipe


def valid_coastline_source_join(source: DeclaredCoastline, request: AuthoredWaterGeometryRequest,
                               context: ResolvedWaterGenerationContext, generation: HydrologyGenerationDecision,
                               region: TerrainRegionExtent, budget: BodyCoverageAllocation, coverage: RegionCoverage,
                               metadata: WaterSourceMetadata, admission: PlacementAdmissionInput,
                               recipe: WaterFieldRecipe | None, implementation: DesignedWaterStrategy) -> None:
    result = CoastlineWaterSourceAdapter().prepare_source(source, geometry_request=request,
        context=context, generation=generation, region=region, budget=budget, region_coverage=coverage,
        metadata=metadata, admission=admission, field_policy=recipe)
    assert_type(result, CoastlineWaterDesignInput)
    assert_type(result.source, CoastlineWaterSource)
    assert_type(implementation.design(result), WaterDesignDraft)


from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy


def valid_continental_noise(input: NoiseWaterDesignInput) -> None:
    implementation: DesignedWaterStrategy = ContinentalNoiseStrategy()
    assert_type(implementation, ContinentalNoiseStrategy)
    assert_type(input.z_min, FineZ)
    assert_type(NoiseFieldGenerator().build(input), ContinentalField)
    assert_type(NoiseFieldGenerator().sample(input.field_policy,x=0.5,y=1.5), float)
    assert_type(ContinentalNoiseStrategy().design(input), ProceduralWaterDesignDraft)


from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateStrategy import PlateStrategy
from app.dataModel.terrain.designedWater.fields.plateLayout import PlateLayout, PlateCenter
from app.dataModel.spatial.grid.coordinateTypes import FineXY


def valid_plate_field(input: PlateWaterDesignInput) -> None:
    implementation: DesignedWaterStrategy = PlateStrategy()
    assert_type(implementation, PlateStrategy)
    layout = PlateFieldGenerator().layout(input.field_policy)
    assert_type(layout, PlateLayout)
    assert_type(layout.centers[0], PlateCenter)
    assert_type(layout.centers[0].cell, FineXY)
    assert_type(layout.effective_count, int)
    assert_type(PlateFieldGenerator().sample(layout, x=0.5, y=1.5), float)
    assert_type(PlateFieldGenerator().build(input), ContinentalField)
    assert_type(PlateStrategy().design(input), ProceduralWaterDesignDraft)


from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy
from app.dataModel.terrain.designedWater.fields.field import PlateRecipe, NoiseRecipe


def valid_composition(input: PlateNoiseWaterDesignInput) -> None:
    implementation: DesignedWaterStrategy = PlateNoiseStrategy()
    assert_type(implementation, PlateNoiseStrategy)
    assert_type(input.field_policy.plate_recipe, PlateRecipe)
    assert_type(input.field_policy.noise_recipe, NoiseRecipe)
    plate = PlateFieldGenerator().build(input)
    noise = NoiseFieldGenerator().build(input)
    assert_type(ContinentalFieldComposer().combine(plate, noise, input.field_policy), ContinentalField)
    assert_type(ContinentalFieldComposer().combine(plate, None, input.field_policy), ContinentalField)
    layout = PlateFieldGenerator().layout(input.field_policy.plate_recipe)
    assert_type(ContinentalFieldComposer().sample(input.field_policy, layout, x=.5, y=.5), float)
    assert_type(PlateNoiseStrategy().design(input), ProceduralWaterDesignDraft)


from app.application.worldData.generators.hydrology.sources.waterSourceMetadataFactory import WaterSourceMetadataFactory
from app.application.worldData.generators.hydrology.basinSpecFactory import basin_specs
from app.application.worldData.placement.adapters.waterTypes import PreparedWaterEntry, WaterPlacementPreparation
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.placement import PreparedPlacement, ResolvedWaterPlacement
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec


def valid_metadata_transport(source: WaterDesignSource, metadata: WaterSourceMetadata,
                             prepared: PreparedPlacement, preparation: WaterPlacementPreparation,
                             records: tuple[ResolvedWaterPlacement, ...], seas: HydrologySeasPolicy,
                             lakes: HydrologyLakesPolicy) -> None:
    assert_type(WaterSourceMetadataFactory().build(source, default_water_level=FineZ(0),
        seas=seas, lakes=lakes, rim_level=None, source_path=("water_sources", "source")), WaterSourceMetadata)
    entry = PreparedWaterEntry(source=metadata, prepared=prepared, floor_z=FineZ(-5), floor_profile=None)
    assert_type(entry.source, WaterSourceMetadata)
    assert_type(entry.floor_profile, BasinFloorProfile | None)
    assert_type(basin_specs(preparation, records), list[BasinSpec])


from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import BasinFloorEvaluator
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace


def valid_basin_floor(input: NoiseWaterDesignInput, spec: BasinSpec, heightmap: SurfaceHeightmap) -> None:
    assert_type(spec.floor_profile, BasinFloorProfile | None)
    if isinstance(spec.floor_profile, FieldFloorProfile):
        evaluator = BasinFloorEvaluator(spec.floor_profile, topology=input.topology,
            coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, grid=input.grid)
        assert_type(evaluator.sample((0, 0)), FineZ)
    assert_type(apply_basin_z(heightmap, (spec,), input.topology, reserved=frozenset(), grid=input.grid), int)


from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, MaterialSupportEntry
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTerrainCondition import ReliefTerrainCondition


def valid_support_sources(value: SurfaceSupportInput, material: MaterialSupportEntry) -> None:
    assert_type(material.substrate, MaterialSubstrateKind | None)
    assert_type(value.templates, tuple[tuple[EntityUid, ReliefTemplate], ...])
    assert_type(value.templates[0][1].conditions, tuple[ReliefTerrainCondition, ...])
    assert_type(value.templates[0][1].structure_refs, tuple[str, ...])
    assert_type(value.terrain_entries[0].hills_authored, bool)


from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceCoatingSupportProvider, SurfaceSupportDependencies, CoatingPlanProvider
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import CoatingPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceCoatingFacts, SurfaceSupportPlan, CoatingPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage


def valid_coating(request: PlanRequest[SurfaceSupportInput], dependencies: SurfaceSupportDependencies,
                  cells: RegionCoverage, inputs: CoatingPlanInput, support: SurfaceSupportPlan,
                  hydrology: HydrologyPlan) -> None:
    assert_type(SurfaceCoatingSupportProvider.facts(request, dependencies, cells=cells), tuple[SurfaceCoatingFacts, ...])
    assert_type(CoatingPlanProvider.plan(inputs, support, hydrology, fine_span=2), PlanBuildResult[CoatingPlan])


from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateLocalPlanProvider
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope


def valid_geo_consumer_bindings(base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
                               final: RegisteredPlanContract[HydrologyFinalInput, GeoHydrologyPlan],
                               support: RegisteredPlanContract[SurfaceSupportInput, SurfaceSupportPlan],
                               deps: SurfaceSupportDependencies[GeoHydrologyPlan],
                               request: PlanRequest[SurfaceSupportInput], cells: RegionCoverage) -> None:
    assert_type(ClimateLocalPlanProvider(base, final), ClimateLocalPlanProvider[GeoHydrologyPlan])
    assert_type(CoatingPlanProvider(support, final, fine_span=2), CoatingPlanProvider[GeoHydrologyPlan])
    assert_type(deps.hydrology, PlanEnvelope[GeoHydrologyPlan])
    assert_type(SurfaceCoatingSupportProvider.facts(request, deps, cells=cells), tuple[SurfaceCoatingFacts, ...])
