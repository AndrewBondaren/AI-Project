"""Bind captured generation sources through the common cascade and policy compiler."""

from dataclasses import dataclass

from app.application.cascade.cascadeLink import Link
from app.application.cascade.contextResolver import extend
from app.application.policy.declarations.compiler import compile_value_policy
from app.application.planning.service.planningService import PlanBuildControl
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.cascade.cascadeGraph import bind_field
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.categorySource import HydrologyCategoryFields
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    BodyWaterGenerationSettings, CategoryWaterGenerationSettings,
    WorldHydrologyGenerationFields, WorldWaterGenerationSettings,
)
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import HYDROLOGY_GENERATION_POLICY
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource, SourcePath
from app.dataModel.policy.policySpec import ValueSelectionPolicySpec
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


@dataclass(frozen=True)
class HydrologyGenerationBinding:
    spec: ValueSelectionPolicySpec[HydrologyExecutionMode, WaterPolicyReason]
    inputs: PolicyInputs
    facts: PolicyFacts
    context: WaterGenerationContext


def resolve_hydrology_category_policies(
    *, categories: HydrologyCategoryFields, enabled: bool, generation: WorldWaterGenerationSettings,
    defaults: WaterGenerationDefaults, mode: ResolutionMode, resolver: PolicyResolver, control: PlanBuildControl,
) -> tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...]:
    """Classify captured categories through their declared channels and common policy."""
    decisions: list[tuple[WaterGenerationCategory, HydrologyGenerationDecision]] = []
    for source in categories.category_sources:
        control.raise_if_shutdown()
        binding = bind_hydrology_generation_policy(enabled=enabled, generation=generation,
            defaults=defaults, category=source.generation.select(categories), root_path=(),
            context_path=(bind_field(source.generation).field,))
        decisions.append((source.category, resolver.resolve(binding.spec, binding.inputs, binding.facts, mode=mode)))
    return tuple(decisions)


def bind_hydrology_generation_policy(
    *, enabled: bool, generation: WorldWaterGenerationSettings,
    defaults: WaterGenerationDefaults, category: CategoryWaterGenerationSettings,
    root_path: SourcePath, context_path: SourcePath,
    body: BodyWaterGenerationSettings | None = None,
) -> HydrologyGenerationBinding:
    root = WorldHydrologyGenerationFields(enabled=enabled, generation=generation)
    # Revalidate even forged model_copy inputs before cascade resolution. Disabled
    # root does not turn malformed authored settings into a valid empty context.
    defaults = WaterGenerationDefaults.model_validate(defaults)
    category = CategoryWaterGenerationSettings.model_validate(category)
    if body is not None:
        body = BodyWaterGenerationSettings.model_validate(body)
    context = WaterGenerationContext.root(root, default_sources=(defaults,))
    context = extend(context, Link(Scope.WORLD, root.generation))
    context = extend(context, Link(Scope.CATEGORY, category))
    if body is not None:
        context = extend(context, Link(Scope.WATER_BODY, body))
    spec = compile_value_policy(HYDROLOGY_GENERATION_POLICY,
                                (WorldHydrologyGenerationFields, WaterGenerationContext))
    return HydrologyGenerationBinding(spec=spec, inputs=PolicyInputs(models=(
        PolicySource(WorldHydrologyGenerationFields, root, root_path),
        PolicySource(WaterGenerationContext, context, context_path),
    )), facts=PolicyFacts(), context=context)
