"""Bind normalized domain values to declarations; never execute policy here."""

from dataclasses import dataclass, replace

from pydantic import TypeAdapter

from app.application.policy.declarations.compiler import compile_admission_policy
from app.application.worldData.generators.hydrology.policy.hydrologyPolicyFacts import collect_hydrology_policy_facts
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.hydrology.placement.placementFields import WaterCategoryPlacementFields, WaterSourcePlacementFields
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    BOUNDARY_PURPOSE, HYDROLOGY_PLACEMENT_POLICY, HydrologyPlacementBehaviorInputs,
    HydrologyPlacementCase, HydrologyPlacementGateInputs, HydrologyPolicyFacts,
    HydrologyPolicySnapshot, WaterPlacementPolicySource,
    HydrologyProceduralGenerationInputs, PROCEDURAL_GENERATION_CASES,
    HydrologyProceduralExtentFacts, PROCEDURAL_EXTENT_CASE, PROCEDURAL_EXTENT_FALLBACK,
)
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import (
    AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource,
)
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.objectAdmissionPolicyDefinition import PlacementPolicyDefaults
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource, SourcePath
from app.dataModel.policy.policyRules import DisableEffect, RequireSupportEffect
from app.dataModel.policy.policySpec import ObjectAdmissionPolicySpec
from app.dataModel.policy.policyEnums import PolicyStage, PolicyState
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind

_SOURCE = TypeAdapter[WaterPlacementPolicySource](WaterPlacementPolicySource)
_UID = TypeAdapter(EntityUid)
_GENERATION = TypeAdapter[HydrologyGenerationDecision](HydrologyGenerationDecision)


@dataclass(frozen=True)
class HydrologyPlacementBinding:
    """Compiled inputs ready for the caller's existing PolicyResolver."""

    spec: ObjectAdmissionPolicySpec[DesignedWaterStrategyKind, WaterPolicyReason]
    inputs: PolicyInputs
    facts: PolicyFacts


def bind_hydrology_placement_policy[H: HydrologyPlan](
    source: WaterPlacementPolicySource,
    category: HydrologySeasPolicy | HydrologyLakesPolicy,
    gates: HydrologyPlacementGateInputs,
    behavior: HydrologyPlacementBehaviorInputs,
    snapshot: HydrologyPolicySnapshot[H],
    *, source_path: SourcePath, category_path: SourcePath,
    generation: HydrologyGenerationDecision | None = None,
    procedural_extent: HydrologyProceduralExtentFacts | None = None,
) -> HydrologyPlacementBinding:
    if not isinstance(source, (DeclaredCoastline, AuthoredBasinSource, AuthoredLakeSource,
                               CoastlineWaterSource, ProceduralSource)):
        raise ValueError("placement binding requires a normalized typed source")
    if not isinstance(category, (HydrologySeasPolicy, HydrologyLakesPolicy)):
        raise ValueError("placement binding requires a typed category owner")
    if not isinstance(gates, HydrologyPlacementGateInputs) or not isinstance(behavior, HydrologyPlacementBehaviorInputs):
        raise ValueError("placement binding requires typed gate/behavior inputs")
    if isinstance(source, DeclaredCoastline):
        # Legacy boundary POJO does not revalidate instances. This is its explicit
        # normalization boundary, analogous to existing WaterDesignSource wrappers.
        source = DeclaredCoastline.model_validate(source.model_dump(warnings=False))
        _UID.validate_python(source.location_uid, strict=True)
    source = _SOURCE.validate_python(source, strict=True)
    gates = HydrologyPlacementGateInputs.model_validate(gates)
    behavior = HydrologyPlacementBehaviorInputs.model_validate(behavior)
    observations = collect_hydrology_policy_facts(source, snapshot)
    if (observations.category is WaterGenerationCategory.LAKE) != isinstance(category, HydrologyLakesPolicy):
        raise ValueError("water category owner does not match the source")
    value = source if isinstance(source, DeclaredCoastline) else source.value
    policy = HYDROLOGY_PLACEMENT_POLICY
    generation_sources: tuple[PolicySource, ...] = ()
    extent_sources: tuple[PolicySource, ...] = ()
    if generation is not None:
        if not isinstance(source, ProceduralSource):
            raise ValueError("computed procedural generation requires a native procedural source")
        resolved_generation = _GENERATION.validate_python(generation, strict=True)
        if resolved_generation.state not in (PolicyState.READY, PolicyState.DISABLED) or resolved_generation.issues:
            raise ValueError("procedural admission requires a terminal generation behavior without fallback")
        execution_mode = resolved_generation.require_behavior()
        if (resolved_generation.state is PolicyState.DISABLED) != (execution_mode is HydrologyExecutionMode.DISABLED):
            raise ValueError("procedural generation state must agree with its execution mode")
        mode = HydrologyProceduralGenerationInputs(execution_mode=execution_mode)
        if procedural_extent is None:
            raise ValueError("native procedural admission requires explicit captured extent facts")
        extent = HydrologyProceduralExtentFacts.model_validate(procedural_extent, strict=True)
        extent_sources = (PolicySource(HydrologyProceduralExtentFacts, extent, (*source_path, "extent")),)
        generation_sources = (PolicySource(HydrologyProceduralGenerationInputs, mode,
            (*source_path, "resolved_generation")),)
    spec = compile_admission_policy(policy, (
        WaterSourcePlacementFields, WaterCategoryPlacementFields, PlacementPolicyDefaults,
        HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs, HydrologyPolicyFacts))
    if generation is not None:
        # Keep field metadata attached to the original descriptor, as for the
        # separately bound target-support cases below.
        mode_spec = compile_admission_policy(replace(policy,
            cases=(*PROCEDURAL_GENERATION_CASES, PROCEDURAL_EXTENT_CASE),
            fallback_rules=(*policy.fallback_rules, PROCEDURAL_EXTENT_FALLBACK)), (
            WaterSourcePlacementFields, WaterCategoryPlacementFields, PlacementPolicyDefaults,
            HydrologyProceduralGenerationInputs, HydrologyProceduralExtentFacts))
        spec = replace(spec, rules=(*spec.rules, *(rule for rule in mode_spec.rules
            if isinstance(rule.effect, DisableEffect) and rule.stage in (PolicyStage.ABSOLUTE_GATE, PolicyStage.SUPPORT))),
            fallback_rules=mode_spec.fallback_rules)
    if isinstance(value, DeclaredCoastline) and value.target_source_uid is not None:
        # Structural target binding only: the generic support stage decides its state.
        # Attached field metadata retains its descriptor identity. Compile the bound
        # compound case separately, with no field metadata, through the same compiler.
        support_policy = replace(policy, cases=(PolicyCaseDeclaration(
            key=HydrologyPlacementCase.TARGET_SUPPORT, conditions=(BOUNDARY_PURPOSE,),
            effect=RequireSupportEffect((value.target_source_uid,))),))
        support_spec = compile_admission_policy(support_policy, (
            WaterSourcePlacementFields, WaterCategoryPlacementFields, PlacementPolicyDefaults, HydrologyPolicyFacts))
        spec = replace(spec, rules=(*spec.rules, *(rule for rule in support_spec.rules
            if isinstance(rule.effect, RequireSupportEffect))))
    inputs = PolicyInputs(models=(
        PolicySource(WaterSourcePlacementFields,
            WaterSourcePlacementFields(placement_specificity=value.placement_specificity), source_path),
        PolicySource(WaterCategoryPlacementFields,
            WaterCategoryPlacementFields(placement_specificity=category.placement_specificity), category_path),
        PolicySource(PlacementPolicyDefaults, PlacementPolicyDefaults.canonical_defaults(), ("placement_defaults",)),
        PolicySource(HydrologyPlacementGateInputs, gates, ("hydrology", "placement_gates")),
        PolicySource(HydrologyPlacementBehaviorInputs, behavior, ("hydrology", "resolved_generation")),
        *generation_sources))
    facts = PolicyFacts(models=(PolicySource(HydrologyPolicyFacts, observations, ("hydrology", "facts")), *extent_sources),
                        supports=snapshot.supports)
    return HydrologyPlacementBinding(spec=spec, inputs=inputs, facts=facts)
