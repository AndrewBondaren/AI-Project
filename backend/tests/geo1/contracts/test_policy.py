"""G0-PT: declarations validate types; they never execute policy decisions."""

import ast
from dataclasses import FrozenInstanceError, replace
from enum import Enum, StrEnum
from pathlib import Path
import unittest

from pydantic import BaseModel, ConfigDict, StrictBool, TypeAdapter, ValidationError

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.policy.declarations.policyIdentity import CommonPolicyOwner, RuleIdentity, RuleKind, make_rule_id
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.objectAdmissionPolicyDefinition import (
    EnabledGate, ObjectAdmissionBindings, ObjectAdmissionFacts, ObjectAdmissionPolicyDefinition, PlacementPolicyDefaults,
)
from app.dataModel.policy.policyDecision import (
    ObjectAdmissionDecision, PolicyDecision, PolicyProvenance, PolicyReason, ValueSelectionDecision,
)
from app.dataModel.policy.policyEnums import (
    FactState, PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyOrigin,
    PolicyRuleId, PolicyStage, PolicyState, RulePrecedence,
)
from app.dataModel.policy.policyReferences import (
    DirectValueRef, FactValueRef, PriorityValueRef,
)
from app.dataModel.policy.policyRules import (
    DisableEffect, Equal, InSet, IsPresent, PolicyFallback, PolicyRule, RequireSupportEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect,
)
from app.dataModel.policy.policyFacts import (
    FactValue, KnownFact, UnknownFact, WaitingFact,
)
from app.dataModel.policy.policySpec import (
    ObjectAdmissionPolicySpec, ValueSelectionPolicySpec,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class WaterAction(StrEnum):
    DECLARED = "declared"
    AUTO = "auto"


class CoatingAction(StrEnum):
    KEEP = "keep"
    APPLY = "apply"


class Reason(StrEnum):
    SOURCE = "source"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    enabled: StrictBool = True
    priority: Specificity | None = None
    action: WaterAction = WaterAction.DECLARED


class Category(BaseModel):
    model_config = Settings.model_config
    priority: Specificity = 7


class Observations(BaseModel):
    model_config = Settings.model_config
    wet: FactValue[bool]


ENABLED = DirectValueRef(FieldRef(lambda: Settings, lambda settings: settings.enabled))
AUTHORED = PriorityValueRef(FieldRef(lambda: Settings, lambda settings: settings.priority))
DOMAIN = PriorityValueRef(FieldRef(lambda: Category, lambda settings: settings.priority))
TERMINAL = PriorityValueRef(FieldRef(lambda: PlacementPolicyDefaults, lambda settings: settings.placement_specificity))
ACTION = DirectValueRef(FieldRef(lambda: Settings, lambda settings: settings.action))
WET = FactValueRef(FieldRef(lambda: Observations, lambda facts: facts.wet))


def behavior_rule(action=WaterAction.AUTO, *, name="auto", precedence=3):
    return PolicyRule(id=PolicyRuleId(name), stage=PolicyStage.BEHAVIOR,
        precedence=RulePrecedence(precedence), conditions=(Equal(WET, True),),
        effect=SelectBehaviorEffect(action), domain_reason=Reason.SOURCE)


def bindings():
    return ObjectAdmissionBindings[WaterAction, Reason](enabled_gates=(EnabledGate(ENABLED),),
        authored_priority_ref=AUTHORED, domain_priority_ref=DOMAIN, terminal_priority_ref=TERMINAL,
        expected_behavior_type=WaterAction, rules=(behavior_rule(),))


def decision_values(operation=PolicyOperation.OBJECT_ADMISSION, **changes):
    values = dict(operation=operation, state=PolicyState.READY, effective_priority=7,
        behavior=WaterAction.AUTO, reasons=(), waiting_supports=(), provenance=(), issues=())
    values.update(changes)
    return values


class FactContractTests(unittest.TestCase):
    def test_known_none_is_not_unknown_or_waiting(self):
        known = KnownFact[bool | None](value=None)
        unknown = UnknownFact(issue=FieldPathError(("wet",), "not available"))
        waiting = WaitingFact(support_uids=("support",))
        self.assertEqual((known.state, unknown.state, waiting.state),
            (FactState.KNOWN, FactState.UNKNOWN, FactState.WAITING))
        self.assertIsNone(known.value)
        adapter = TypeAdapter(FactValue[bool | None])
        for value in (known, unknown, waiting):
            self.assertEqual(adapter.validate_python(value, strict=True), value)

    def test_fact_value_payload_and_supports_are_strict_and_frozen(self):
        for uids in ((), ("same", "same"), (" ",), ["list"]):
            with self.assertRaises(ValidationError):
                WaitingFact(support_uids=uids)
        with self.assertRaises(ValidationError):
            KnownFact[bool](value=1)
        fact = KnownFact[bool](value=True)
        with self.assertRaises(ValidationError):
            fact.value = False
        with self.assertRaises(ValidationError):
            Observations(wet=KnownFact[str](value="not bool"))
        for value in ([1], {"mutable": 1}, {1}, float("nan"), float("inf")):
            with self.assertRaises(ValidationError):
                KnownFact(value=value)


class DeclarationTests(unittest.TestCase):
    def test_ref_reuses_fieldref_and_preserves_heterogeneous_model_identity(self):
        self.assertIs(AUTHORED.bound_field.model, Settings)
        self.assertIs(DOMAIN.bound_field.model, Category)
        self.assertEqual(AUTHORED.bound_field.field, "priority")
        self.assertEqual(Equal(ACTION, WaterAction.AUTO).expected, WaterAction.AUTO)
        self.assertEqual(InSet(WET, frozenset({True, False})).values, frozenset({True, False}))
        self.assertIs(IsPresent(WET).reference, WET)

    def test_scalar_fact_expected_and_priority_type_mismatches_fail_at_declaration(self):
        with self.assertRaises(ValueError):
            FactValueRef(FieldRef(lambda: Settings, lambda settings: settings.enabled))
        with self.assertRaises(ValueError):
            DirectValueRef(FieldRef(lambda: Observations, lambda facts: facts.wet))
        for value in (1, "true", WaterAction.AUTO):
            with self.assertRaises(ValidationError):
                Equal(WET, value)
        with self.assertRaises(ValidationError):
            Equal(ACTION, CoatingAction.APPLY)
        with self.assertRaises(ValueError):
            PriorityValueRef(FieldRef(lambda: Settings, lambda settings: settings.enabled))

    def test_ref_requires_direct_field_and_frozen_revalidated_pojo(self):
        class Mutable(BaseModel):
            enabled: bool
        with self.assertRaises(ValueError):
            DirectValueRef(FieldRef(lambda: Mutable, lambda settings: settings.enabled))
        with self.assertRaises(ValueError):
            DirectValueRef(FieldRef(lambda: Settings, lambda settings: not settings.enabled))
        with self.assertRaises(ValueError):
            DirectValueRef(FieldRef(lambda: Settings, lambda settings: settings.model_config["frozen"]))

    def test_rule_identity_precedence_stage_and_effect_are_validated(self):
        rule = behavior_rule()
        for changes in (dict(id=""), dict(id=" spaced "), dict(precedence=-1), dict(precedence=True),
                        dict(stage="behavior"), dict(stage=PolicyStage.SUPPORT), dict(conditions=[]),
                        dict(conditions=(lambda: True,))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(rule, **changes)
        with self.assertRaises(FrozenInstanceError):
            rule.precedence = RulePrecedence(99)
        with self.assertRaises(ValueError):
            RequireSupportEffect(support_uids=())
        support = PolicyRule(id=PolicyRuleId("support"), stage=PolicyStage.SUPPORT,
            precedence=RulePrecedence(2), conditions=(), effect=RequireSupportEffect(("parent",)))
        default = PolicyRule(id=PolicyRuleId("default"), stage=PolicyStage.PRIORITY,
            precedence=RulePrecedence(4), conditions=(), effect=SelectPriorityDefaultEffect(DOMAIN))
        self.assertEqual(support.effect.support_uids, ("parent",))
        self.assertIs(default.effect.ref, DOMAIN)

    def test_unique_rules_and_fallbacks_and_bound_behavior_enum(self):
        spec = ObjectAdmissionPolicyDefinition.build(bindings())
        for changes in (dict(rules=(behavior_rule(), behavior_rule())),
                        dict(rules=(behavior_rule(CoatingAction.APPLY),)),
                        dict(fallback_rules=(PolicyFallback(PolicyIssueReason.UNKNOWN_FACT, CoatingAction.KEEP, True),)),
                        dict(fallback_rules=(spec.fallback_rules[0], spec.fallback_rules[0]))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(spec, **changes)

    def test_two_domain_definitions_share_common_contracts_without_evaluation(self):
        object_spec = ObjectAdmissionPolicyDefinition.build(bindings())
        coating_rule = PolicyRule[CoatingAction, Reason](id=PolicyRuleId("coat"),
            stage=PolicyStage.BEHAVIOR, precedence=RulePrecedence(1), conditions=(Equal(WET, True),),
            effect=SelectBehaviorEffect(CoatingAction.KEEP), domain_reason=Reason.SOURCE)
        value_spec = ValueSelectionPolicySpec[CoatingAction, Reason](
            operation=PolicyOperation.VALUE_SELECTION, rules=(coating_rule,),
            expected_behavior_type=CoatingAction, fallback_rules=())
        self.assertEqual(object_spec.operation, PolicyOperation.OBJECT_ADMISSION)
        self.assertEqual(value_spec.rules[0].effect.value, CoatingAction.KEEP)
        # Potential equal-precedence conflicts require matched facts in G0-PE.
        replace(object_spec, rules=(behavior_rule(name="a"), behavior_rule(WaterAction.DECLARED, name="b")))

    def test_common_definition_owns_enabled_and_computed_zero_gate(self):
        original = bindings()
        spec = ObjectAdmissionPolicyDefinition.build(original)
        self.assertIs(spec.authored_priority_ref, AUTHORED)
        self.assertIs(spec.domain_priority_ref, DOMAIN)
        self.assertEqual(PlacementPolicyDefaults.canonical_defaults().placement_specificity, 0)
        zero_id = make_rule_id(RuleIdentity(owner=CommonPolicyOwner, kind=RuleKind.ZERO_PRIORITY))
        zero = next(rule for rule in spec.rules if rule.id == zero_id)
        self.assertIs(zero.conditions[0].reference.bound_field.model, ObjectAdmissionFacts)
        self.assertEqual(zero.conditions[0].expected, 0)
        self.assertEqual(zero.effect.reason, PolicyDisableReason.ZERO_PRIORITY)
        self.assertEqual(len(original.rules), 1)
        self.assertEqual({fallback.reason for fallback in spec.fallback_rules}, {PolicyIssueReason.UNKNOWN_FACT})
        with self.assertRaises(ValueError):
            ObjectAdmissionPolicyDefinition.build(replace(original, enabled_gates=(WET,)))
        with self.assertRaises(ValueError):
            replace(spec, operation=PolicyOperation.VALUE_SELECTION)
        with self.assertRaises(ValueError):
            ValueSelectionPolicySpec(operation=PolicyOperation.VALUE_SELECTION, rules=spec.rules,
                expected_behavior_type=WaterAction, fallback_rules=())


class DecisionTests(unittest.TestCase):
    def test_operation_and_behavior_binding_and_readonly_covariant_result(self):
        object_decision = ObjectAdmissionDecision[WaterAction, Reason](**decision_values())
        generic: PolicyDecision[Enum, Enum] = object_decision
        self.assertEqual(generic.require_behavior(), WaterAction.AUTO)
        value = ValueSelectionDecision[WaterAction, Reason](**decision_values(
            operation=PolicyOperation.VALUE_SELECTION, effective_priority=None))
        self.assertEqual(value.require_behavior(), WaterAction.AUTO)
        with self.assertRaises(ValidationError):
            object_decision.behavior = WaterAction.DECLARED
        with self.assertRaises(ValidationError):
            ObjectAdmissionDecision[WaterAction, Reason](**decision_values(behavior=CoatingAction.APPLY))

    def test_invalid_ready_waiting_unresolved_and_operation_combinations(self):
        for changes in (dict(effective_priority=0), dict(effective_priority=None), dict(effective_priority=True),
                        dict(state=PolicyState.WAITING_SUPPORT), dict(state=PolicyState.UNRESOLVED),
                        dict(operation=PolicyOperation.VALUE_SELECTION), dict(waiting_supports=("p",)),
                        dict(issues=(FieldPathError((), "bad"),))):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ObjectAdmissionDecision[WaterAction, Reason](**decision_values(**changes))
        with self.assertRaises(ValidationError):
            ValueSelectionDecision[WaterAction, Reason](**decision_values(operation=PolicyOperation.VALUE_SELECTION))
        with self.assertRaises(ValidationError):
            ValueSelectionDecision[WaterAction, Reason](**decision_values(operation=PolicyOperation.VALUE_SELECTION,
                effective_priority=None, behavior=None))

    def test_disabled_fallback_retains_issue_provenance_and_domain_reason(self):
        provenance = PolicyProvenance(origin=PolicyOrigin.FALLBACK, source_path=("sources", "uid", 0), rule_id=None)
        reason = PolicyReason[Reason](domain_reason=Reason.SOURCE, common_reason=PolicyDisableReason.ERROR_FALLBACK)
        issue = FieldPathError(("support",), "missing")
        result = ObjectAdmissionDecision[WaterAction, Reason](**decision_values(state=PolicyState.DISABLED,
            effective_priority=None, behavior=None, reasons=(reason,), provenance=(provenance,), issues=(issue,)))
        self.assertEqual(result.issues, (issue,))
        self.assertEqual(result.reasons[0].domain_reason, Reason.SOURCE)
        with self.assertRaises(ValueError):
            result.require_behavior()
        with self.assertRaises(ValidationError):
            PolicyProvenance(origin=PolicyOrigin.RULE, source_path=(), rule_id=None)

    def test_copied_invalid_decision_is_revalidated(self):
        valid = ObjectAdmissionDecision[WaterAction, Reason](**decision_values())
        forged = valid.model_copy(update={"effective_priority": 0})
        with self.assertRaises(ValidationError):
            ObjectAdmissionDecision[WaterAction, Reason].model_validate(forged)

    def test_policy_modules_have_no_domain_executor_or_application_imports(self):
        root = Path(__file__).resolve().parents[3] / "app/dataModel/policy"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn("application", node.module or "")
                    self.assertNotIn("hydrology", node.module or "")
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name, ("resolve", "evaluate", "apply"))


if __name__ == "__main__":
    unittest.main()
