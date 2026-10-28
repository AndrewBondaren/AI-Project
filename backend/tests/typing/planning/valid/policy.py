"""Positive policy contracts; checked statically by Pyright."""

from enum import Enum, StrEnum
from typing import assert_type

from pydantic import BaseModel, ConfigDict, StrictBool

from app.application.policy.declarations.compiler import compile_admission_policy, compile_value_policy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import HYDROLOGY_AUTORESOLVE, HYDROLOGY_GENERATION_POLICY
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyOwner, ValuePolicy
from app.dataModel.policy.objectAdmissionPolicyDefinition import (
    EnabledGate,
    ObjectAdmissionBindings,
    ObjectAdmissionPolicyDefinition,
    PlacementPolicyDefaults,
)
from app.dataModel.policy.policyBindings import PolicyFacts as PolicyObservations, PolicyInputs, PolicySource
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyDecision, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyRuleId, PolicyStage, RulePrecedence
from app.dataModel.policy.policyFacts import FactValue, KnownFact
from app.dataModel.policy.policyReferences import DirectValueRef, FactValueRef, PriorityValueRef
from app.dataModel.policy.policyRules import Equal, InSet, IsPresent, PolicyRule, SelectBehaviorEffect
from app.dataModel.policy.policySpec import ObjectAdmissionPolicySpec, ValueSelectionPolicySpec
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


class PolicyMode(StrEnum):
    FIRST = "first"
    SECOND = "second"


class OtherPolicyMode(StrEnum):
    OTHER = "other"


class PolicyReasonKind(StrEnum):
    DECLARED = "declared"


class OtherPolicyReason(StrEnum):
    OTHER = "other"


class PolicySettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    enabled: StrictBool
    priority: Specificity | None
    mode: PolicyMode


class PolicyDefaults(BaseModel):
    model_config = PolicySettings.model_config
    priority: Specificity


class PolicyFacts(BaseModel):
    model_config = PolicySettings.model_config
    flag: FactValue[bool]


def valid_policy_definitions() -> ObjectAdmissionPolicySpec[PolicyMode, PolicyReasonKind]:
    enabled = DirectValueRef[PolicySettings, bool](FieldRef(lambda: PolicySettings, lambda s: s.enabled))
    mode = DirectValueRef[PolicySettings, PolicyMode](FieldRef(lambda: PolicySettings, lambda s: s.mode))
    fact = FactValueRef[PolicyFacts, bool](FieldRef(lambda: PolicyFacts, lambda f: f.flag))
    rule = PolicyRule[PolicyMode, PolicyReasonKind](id=PolicyRuleId("mode"), stage=PolicyStage.BEHAVIOR,
        precedence=RulePrecedence(1), conditions=(Equal(fact, True), InSet(mode, frozenset({PolicyMode.FIRST})),
            IsPresent(fact)), effect=SelectBehaviorEffect(PolicyMode.FIRST), domain_reason=PolicyReasonKind.DECLARED)
    authored = PriorityValueRef[PolicySettings](FieldRef(lambda: PolicySettings, lambda s: s.priority))
    domain = PriorityValueRef[PolicyDefaults](FieldRef(lambda: PolicyDefaults, lambda s: s.priority))
    terminal = PriorityValueRef[PlacementPolicyDefaults](FieldRef(lambda: PlacementPolicyDefaults, lambda s: s.placement_specificity))
    spec = ObjectAdmissionPolicyDefinition.build(ObjectAdmissionBindings[PolicyMode, PolicyReasonKind](
        enabled_gates=(EnabledGate(enabled),), authored_priority_ref=authored,
        domain_priority_ref=domain, terminal_priority_ref=terminal,
        expected_behavior_type=PolicyMode, rules=(rule,)))
    assert_type(spec, ObjectAdmissionPolicySpec[PolicyMode, PolicyReasonKind])
    assert_type(ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind](
        operation=PolicyOperation.VALUE_SELECTION, rules=(rule,), expected_behavior_type=PolicyMode,
        fallback_rules=()), ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind])
    return spec


def valid_policy_covariance(admission: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind],
    selection: ValueSelectionDecision[PolicyMode, PolicyReasonKind]) -> PolicyDecision[Enum, Enum]:
    generic: PolicyDecision[Enum, Enum] = admission
    generic = selection
    assert_type(admission.require_behavior(), PolicyMode)
    return generic


def valid_fact_covariance(known: KnownFact[PolicyMode]) -> KnownFact[Enum]:
    return known


def valid_hydrology_generation(root: WorldHydrologyGenerationFields, context: WaterGenerationContext) -> None:
    sources = PolicyInputs(models=(PolicySource(WorldHydrologyGenerationFields, root, ("hydrology",)),
        PolicySource(WaterGenerationContext, context, ("resolved",))))
    spec = compile_value_policy(HYDROLOGY_GENERATION_POLICY, (WorldHydrologyGenerationFields, WaterGenerationContext))
    assert_type(HYDROLOGY_AUTORESOLVE.cases[0].when, bool)
    assert_type(spec, ValueSelectionPolicySpec[HydrologyExecutionMode, WaterPolicyReason])
    decision = PolicyResolver().resolve(spec, sources, PolicyObservations(),
        mode=ResolutionMode.VALIDATE_ONLY)
    assert_type(decision, ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason])
    typed: HydrologyGenerationDecision = decision
    assert_type(typed.require_behavior(), HydrologyExecutionMode)


def valid_policy_execution(settings: PolicySettings, defaults: PolicyDefaults, observed: PolicyFacts,
    admission_spec: ObjectAdmissionPolicySpec[PolicyMode, PolicyReasonKind],
    value_spec: ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind],
    prior: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind]) -> None:
    sources = PolicyInputs(models=(PolicySource[PolicySettings](PolicySettings, settings, ("settings",)),
        PolicySource[PolicyDefaults](PolicyDefaults, defaults, ("defaults",))))
    facts = PolicyObservations(models=(PolicySource[PolicyFacts](PolicyFacts, observed, ("facts",)),))
    assert_type(PolicyResolver().resolve(admission_spec, sources, facts, mode=ResolutionMode.RUNTIME),
        ObjectAdmissionDecision[PolicyMode, PolicyReasonKind])
    assert_type(PolicyResolver().resolve(value_spec, sources, facts, mode=ResolutionMode.VALIDATE_ONLY),
        ValueSelectionDecision[PolicyMode, PolicyReasonKind])
    assert_type(PolicyResolver().resolve(admission_spec, sources, facts, mode=ResolutionMode.RUNTIME, resume=prior),
        ObjectAdmissionDecision[PolicyMode, PolicyReasonKind])


class DeclarationOwner(PolicyOwner):
    pass


VALUE_DECLARATION = ValuePolicy[PolicyMode, PolicyReasonKind](owner=DeclarationOwner,
    behavior_type=PolicyMode, reason_type=PolicyReasonKind)


VALUE_CASE = ValueCase[bool, PolicyMode, PolicyReasonKind](when=False, behavior=PolicyMode.FIRST,
    reason=PolicyReasonKind.DECLARED)


VALUE_METADATA = SelectByValue[bool, PolicyMode, PolicyReasonKind](VALUE_DECLARATION, (VALUE_CASE,))


VALUE_GATE = EnabledFor[PolicyMode, PolicyReasonKind](VALUE_DECLARATION)


def valid_policy_declarations(priority: PriorityValueRef[PolicyDefaults]) -> None:
    assert_type(VALUE_METADATA.cases[0].when, bool)
    assert_type(VALUE_METADATA.cases[0].behavior, PolicyMode)
    assert_type(VALUE_METADATA.cases[0].reason, PolicyReasonKind | None)
    assert_type(VALUE_GATE.policy, ValuePolicy[PolicyMode, PolicyReasonKind] | AdmissionPolicy[PolicyMode, PolicyReasonKind])
    admission = AdmissionPolicy[PolicyMode, PolicyReasonKind](owner=DeclarationOwner,
        behavior_type=PolicyMode, reason_type=PolicyReasonKind, authored_priority_ref=priority,
        domain_priority_ref=priority, terminal_priority_ref=priority)
    assert_type(admission, AdmissionPolicy[PolicyMode, PolicyReasonKind])
    compound = PolicyCaseDeclaration[PolicyMode, PolicyReasonKind](key=PolicyReasonKind.DECLARED,
        conditions=(), effect=SelectBehaviorEffect(PolicyMode.FIRST))
    ValuePolicy[PolicyMode, PolicyReasonKind](owner=DeclarationOwner, behavior_type=PolicyMode,
        reason_type=PolicyReasonKind, cases=(compound,))


def valid_policy_compilation(admission: AdmissionPolicy[PolicyMode, PolicyReasonKind]) -> None:
    assert_type(compile_value_policy(VALUE_DECLARATION, (PolicySettings,)),
        ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind])
    assert_type(compile_admission_policy(admission, (PolicySettings, PolicyDefaults, PlacementPolicyDefaults)),
        ObjectAdmissionPolicySpec[PolicyMode, PolicyReasonKind])


from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy, HydrologyPlacementBinding
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import WaterPlacementPolicySource, HydrologyPolicySnapshot, HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


def valid_water_placement_policy(source: WaterPlacementPolicySource, snapshot: HydrologyPolicySnapshot,
                                 category: HydrologySeasPolicy,
                                 gates: HydrologyPlacementGateInputs,
                                 behavior: HydrologyPlacementBehaviorInputs) -> None:
    binding = bind_hydrology_placement_policy(source, category, gates, behavior, snapshot,
        source_path=("hydrology", "sources", 0), category_path=("hydrology", "default_seas"))
    assert_type(binding, HydrologyPlacementBinding)
    assert_type(PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts,
        mode=ResolutionMode.VALIDATE_ONLY), ObjectAdmissionDecision[DesignedWaterStrategyKind, WaterPolicyReason])
