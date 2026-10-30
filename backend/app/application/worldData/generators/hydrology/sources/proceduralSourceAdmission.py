"""Hydrology owns native category/cascade/evidence/admission bindings and diagnostics."""

from app.application.cascade.cascadeLink import Link
from app.application.cascade.contextResolver import extend
from app.application.jsonValidation.resolve import log_issues
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.dataModel.cascade.runtimeContext import freeze_resolved_context
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category, WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext, WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields
from app.dataModel.hydrology.policy.proceduralSourceAdmission import ResolvedProceduralSource, ProceduralSourceAdmissions
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPlacementBehaviorInputs, HydrologyPlacementGateInputs, HydrologyPolicySnapshot, HydrologyProceduralExtentFacts,
)
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


def _invalid(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "procedural_sources"), message,
        code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))


class ProceduralSourceAdmissionJob:
    def resolve(self, inputs: GeoWaterPlacementInput, batch: PlacementBatchV2,
                water_intents: tuple[PlacementIntent, ...], control: PlanBuildControl) -> ProceduralSourceAdmissions:
        inputs = GeoWaterPlacementInput.model_validate(inputs, strict=True)
        batch = PlacementBatchV2.model_validate(batch, strict=True)
        if inputs.topology != batch.topology:
            raise _invalid("captured topology must match the joint placement batch")
        if any(not isinstance(source, ProceduralSource) for source in inputs.sources):
            raise _invalid("native procedural preparation requires explicit ProceduralSource owners")
        intents = {intent.identity.source_uid: PlacementIntent.model_validate(intent, strict=True) for intent in water_intents}
        if len(intents) != len(water_intents) or intents.keys() != {
                source.value.source_uid for source in inputs.sources if isinstance(source, ProceduralSource)}:
            raise _invalid("native sources require exactly one original placement intent each")
        root = WorldHydrologyGenerationFields(enabled=inputs.enabled, generation=inputs.generation)
        world_context = freeze_resolved_context(extend(WaterGenerationContext.root(root,
            default_sources=(inputs.defaults,)), Link(WaterGenerationScope.WORLD, root.generation)), ResolvedWaterGenerationContext)
        resolver = PolicyResolver()
        evidence = HydrologyPolicySnapshot(world_uid=batch.world_uid, supports=(), hydrology=None,
            source_mapping=None, mapping_hydrology_ref=None)
        bindings: list[ResolvedProceduralSource] = []
        for source in inputs.sources:
            control.raise_if_shutdown()
            if not isinstance(source, ProceduralSource):
                raise _invalid("native procedural preparation requires ProceduralSource")
            uid = source.value.source_uid
            category_id = Category.for_basin_kind(source.value.kind)
            category, settings, path = {
                Category.LAKE: (inputs.lakes, inputs.lake_generation, "default_lakes"),
                Category.OCEAN: (inputs.seas, inputs.ocean_generation, "default_seas"),
                Category.SEA: (inputs.seas, inputs.sea_generation, "default_seas"),
            }[category_id]
            source_path = ("hydrology", "sources", uid)
            gates = HydrologyPlacementGateInputs(world_enabled=inputs.enabled, category_enabled=category.enabled)
            binding = bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation,
                defaults=inputs.defaults, category=settings, body=source.value.generation,
                root_path=("hydrology",), context_path=("water_sources", uid, "context"))
            generation = resolver.resolve(binding.spec, binding.inputs, binding.facts, mode=inputs.resolution_mode)
            context = freeze_resolved_context(binding.context, ResolvedWaterGenerationContext)
            extent = HydrologyProceduralExtentFacts(world_extent=(KnownFact[bool](value=True)
                if inputs.declared_world_bounds is not None else UnknownFact(issue=FieldPathError(
                    ("hydrology", "sources", uid, "world_bounds"), "active procedural source requires declared fixed world bounds",
                    code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value))))
            placement = bind_hydrology_placement_policy(source, category, gates,
                HydrologyPlacementBehaviorInputs(strategy=context.strategy), evidence, source_path=source_path,
                category_path=("hydrology", path), generation=generation, procedural_extent=extent)
            decision = resolver.resolve(placement.spec, placement.inputs, placement.facts, mode=inputs.resolution_mode)
            if inputs.resolution_mode is ResolutionMode.RUNTIME and decision.issues:
                log_issues(decision.issues)
            bindings.append(ResolvedProceduralSource(source=source, context=context, generation=generation,
                admission=PlacementAdmissionInput(header=PlacementHeader.from_intent(intents[uid]), decision=decision),
                source_path=source_path))
        joint = PlacementBatchV2.model_validate(batch.model_copy(update={
            "objects": (*batch.objects, *(binding.admission for binding in bindings))}), strict=True)
        return ProceduralSourceAdmissions(world_context=world_context, sources=tuple(bindings),
            batch=joint, water_intents=water_intents)
