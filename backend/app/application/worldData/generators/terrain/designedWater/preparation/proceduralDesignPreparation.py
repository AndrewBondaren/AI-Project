"""Native source owners → cascade/policy → the common designed-water runner."""

from collections.abc import Callable

from app.application.cascade.cascadeLink import Link
from app.application.cascade.contextResolver import extend
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.application.worldData.generators.hydrology.sources.waterSourceMetadataFactory import WaterSourceMetadataFactory
from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import ProceduralWaterSourceAdapter
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.lifecycle.session import SupportReevaluation
from app.dataModel.cascade.runtimeContext import freeze_resolved_context
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext, WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPlacementBehaviorInputs, HydrologyPlacementGateInputs, HydrologyPolicySnapshot,
)
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.input import WaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _invalid(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "procedural_sources"), message,
        code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))


def prepare_procedural_designed_water(
    inputs: GeoWaterPlacementInput, batch: PlacementBatchV2, *, water_intents: tuple[PlacementIntent, ...],
    pre_hydrology: PlanEnvelope[TerrainPlan], regions: TerrainRegionPlan, seed_root: EntityUid,
    prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    strategies: DesignedWaterStrategyFactory, control: PlanBuildControl,
    reevaluate_support: SupportReevaluation | None = None,
) -> tuple[WaterCoverageBudget | None, tuple[WaterDesignPreparation, ...], PlacementBatchResultV2]:
    """Prepare explicit native procedural sources together with caller competitors.

    Source and placement identities remain caller-owned. Authored wrappers require
    their owning-schema cutover; this entry accepts only native ProceduralSource.
    It creates no default sources and never changes the captured scene or terrain.
    """
    control.raise_if_shutdown()
    inputs = GeoWaterPlacementInput.model_validate(inputs, strict=True)
    batch = PlacementBatchV2.model_validate(batch, strict=True)
    regions = TerrainRegionPlan.model_validate(regions, strict=True)
    pre_hydrology = PlanEnvelope[TerrainPlan].model_validate(pre_hydrology, strict=True)
    if inputs.topology != batch.topology:
        raise _invalid("captured topology must match the joint placement batch")
    sources: dict[EntityUid, ProceduralSource] = {}
    for source in inputs.sources:
        if not isinstance(source, ProceduralSource):
            raise _invalid("native procedural preparation requires explicit ProceduralSource owners")
        sources[source.value.source_uid] = source
    intents = {intent.identity.source_uid: PlacementIntent.model_validate(intent, strict=True) for intent in water_intents}
    if len(intents) != len(water_intents) or intents.keys() != sources.keys():
        raise _invalid("native sources require exactly one original placement intent each")
    root = WorldHydrologyGenerationFields(enabled=inputs.enabled, generation=inputs.generation)
    world_context = freeze_resolved_context(extend(WaterGenerationContext.root(root,
        default_sources=(inputs.defaults,)), Link(WaterGenerationScope.WORLD, root.generation)), ResolvedWaterGenerationContext)
    resolver = PolicyResolver()
    evidence = HydrologyPolicySnapshot(world_uid=batch.world_uid, supports=(), hydrology=None,
        source_mapping=None, mapping_hydrology_ref=None)
    contexts: dict[EntityUid, ResolvedWaterGenerationContext] = {}
    generations: dict[EntityUid, HydrologyGenerationDecision] = {}
    admissions: list[PlacementAdmissionInput] = []
    requests: list[BodyCoverageRequest] = []
    for uid, source in sources.items():
        control.raise_if_shutdown()
        if source.value.kind is BasinKind.LAKE:
            category, settings, path = inputs.lakes, inputs.lake_generation, "default_lakes"
        elif source.value.kind is BasinKind.OCEAN:
            category, settings, path = inputs.seas, inputs.ocean_generation, "default_seas"
        else:
            category, settings, path = inputs.seas, inputs.sea_generation, "default_seas"
        # Capture gates before executing the generation decision. Later work
        # consumes the computed mode and never rereads enabled/autoresolve flags.
        gates = HydrologyPlacementGateInputs(world_enabled=inputs.enabled, category_enabled=category.enabled)
        binding = bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation,
            defaults=inputs.defaults, category=settings, body=source.value.generation,
            root_path=("hydrology",), context_path=("water_sources", uid, "context"))
        generation = resolver.resolve(binding.spec, binding.inputs, binding.facts, mode=inputs.resolution_mode)
        context = freeze_resolved_context(binding.context, ResolvedWaterGenerationContext)
        placement = bind_hydrology_placement_policy(source, category, gates,
            HydrologyPlacementBehaviorInputs(strategy=context.strategy), evidence,
            source_path=("hydrology", "sources", uid), category_path=("hydrology", path), generation=generation)
        decision = resolver.resolve(placement.spec, placement.inputs, placement.facts, mode=inputs.resolution_mode)
        admissions.append(PlacementAdmissionInput(header=PlacementHeader.from_intent(intents[uid]), decision=decision))
        contexts[uid], generations[uid] = context, generation
        if decision.state in (PolicyState.READY, PolicyState.WAITING_SUPPORT):
            if context.strategy is Strategy.AUTHORED_REGION:
                raise _invalid("active native procedural source requires a field strategy")
            if inputs.declared_world_bounds is None:
                raise _invalid("active procedural source requires declared fixed world bounds")
            region = regions.snapshot.region_for(source.value.generation_region_uid)
            if region is None:
                raise _invalid("active source generation region is absent from captured terrain regions")
            requests.append(BodyCoverageRequest(source_uid=uid, generation_region_uid=region.region_uid,
                generation_area_fine2=region.generation_area_fine2, target_fraction=context.water_fraction))

    def prepare_input(admission: PlacementAdmissionInput, budget: WaterCoverageBudget | None) -> WaterStrategyInput:
        uid = admission.header.identity.source_uid
        source, context = sources[uid], contexts[uid]
        if budget is None:
            raise _invalid("ready procedural source requires the shared world budget")
        allocation = next((item for item in budget.allocations if item.source_uid == uid), None)
        region = regions.snapshot.region_for(source.value.generation_region_uid)
        coverage = next((item for item in regions.coverages if item.region_uid == source.value.generation_region_uid), None)
        if allocation is None or region is None or coverage is None:
            raise _invalid("ready source requires its exact allocation and terrain region coverage")
        metadata = WaterSourceMetadataFactory().build(source, default_water_level=inputs.default_water_level,
            seas=inputs.seas, lakes=inputs.lakes, rim_level=None, source_path=("hydrology", "sources", uid))
        shared = WaterDesignInput[ProceduralSource](strategy=context.strategy, source=source, metadata=metadata,
            context=context, region=region, budget=allocation, seed_root=seed_root, topology=inputs.topology,
            grid=inputs.grid, pre_hydrology=pre_hydrology, region_coverage=coverage)
        topology = fine_topology(inputs.topology, inputs.grid.fine_span)
        recipe: WaterFieldRecipe
        if context.strategy is Strategy.CONTINENTAL_NOISE:
            recipe = NoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy)
        elif context.strategy is Strategy.PLATE:
            recipe = PlateRecipe(seed_root=seed_root, topology=topology, plate_policy=inputs.plate_policy)
        elif context.strategy is Strategy.PLATE_NOISE:
            recipe = PlateNoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy,
                plate_policy=inputs.plate_policy, composition_policy=inputs.composition_policy)
        else:
            raise _invalid("native procedural source requires a field recipe")
        return ProceduralWaterSourceAdapter().prepare_source(shared, generation=generations[uid],
            admission=admission, field_policy=recipe, z_min=inputs.z_min)

    joint = PlacementBatchV2.model_validate(batch.model_copy(update={"objects": (*batch.objects, *admissions)}), strict=True)
    return prepare_designed_water(joint, water_intents=water_intents, pre_hydrology=pre_hydrology,
        regions=regions, world_context=world_context, coverage_requests=tuple(requests), authored_geometry=(),
        grid=inputs.grid, seed_root=seed_root, prepare_input=prepare_input, prepare_competitor=prepare_competitor,
        strategies=strategies, selection_policy=inputs.selection_policy, control=control, reevaluate_support=reevaluate_support)
