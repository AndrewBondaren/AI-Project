"""Shared executor semantics across independent policy definitions."""

import ast
from dataclasses import replace
from enum import StrEnum
from itertools import permutations
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, StrictBool

from app.application.policy.policyRead import PolicyReader
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.objectAdmissionPolicyDefinition import (
    EnabledGate, ObjectAdmissionBindings, ObjectAdmissionPolicyDefinition, PlacementPolicyDefaults,
)
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource, PolicySupportFact
from app.dataModel.policy.policyEnums import (
    PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyOrigin, PolicyRuleId,
    PolicyStage, PolicyState, PolicySupportState, RulePrecedence,
)
from app.dataModel.policy.policyFacts import FactValue, KnownFact, UnknownFact, WaitingFact
from app.dataModel.policy.policyReferences import DirectValueRef, FactValueRef, PriorityValueRef
from app.dataModel.policy.policyRules import (
    DisableEffect, Equal, InSet, IsPresent, PolicyFallback, PolicyRule,
    RequireSupportEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect,
)
from app.dataModel.policy.policySpec import ValueSelectionPolicySpec
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


class Action(StrEnum):
    FIRST = "first"
    SECOND = "second"


class OtherAction(StrEnum):
    KEEP = "keep"


class Reason(StrEnum):
    SELECTED = "selected"


class Settings(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    enabled: StrictBool = True
    priority: Specificity | None = None


class Defaults(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    priority: Specificity | None = 3
    alternative: Specificity = 7


class Facts(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    flag: FactValue[bool | None]


ENABLED = DirectValueRef(FieldRef(lambda: Settings, lambda s: s.enabled))
PRIORITY = PriorityValueRef(FieldRef(lambda: Settings, lambda s: s.priority))
DEFAULT = PriorityValueRef(FieldRef(lambda: Defaults, lambda d: d.priority))
ALTERNATIVE = PriorityValueRef(FieldRef(lambda: Defaults, lambda d: d.alternative))
TERMINAL = PriorityValueRef(FieldRef(lambda: PlacementPolicyDefaults, lambda d: d.placement_specificity))
FLAG = FactValueRef(FieldRef(lambda: Facts, lambda f: f.flag))
ERROR = FieldPathError(("observed",), "unknown observation")


def rule(name="choose", *, stage=PolicyStage.BEHAVIOR, effect=None, conditions=(), precedence=1):
    return PolicyRule[Action, Reason](id=PolicyRuleId(name), stage=stage, precedence=RulePrecedence(precedence),
        conditions=conditions, effect=effect or SelectBehaviorEffect(Action.FIRST), domain_reason=Reason.SELECTED)


def admission(rules=(), fallbacks=()):
    return ObjectAdmissionPolicyDefinition.build(ObjectAdmissionBindings[Action, Reason](
        enabled_gates=(EnabledGate(ENABLED),), authored_priority_ref=PRIORITY,
        domain_priority_ref=DEFAULT, terminal_priority_ref=TERMINAL,
        expected_behavior_type=Action, rules=rules, fallback_rules=fallbacks))


def sources(settings=None, defaults=None):
    return PolicyInputs(models=(PolicySource(Settings, settings or Settings(), ("settings",)),
        PolicySource(Defaults, defaults or Defaults(), ("defaults",)),
        PolicySource(PlacementPolicyDefaults, PlacementPolicyDefaults(), ("terminal",))))


def facts(value=True, supports=()):
    return PolicyFacts(models=(PolicySource(Facts, Facts(flag=KnownFact(value=value)), ("facts",)),), supports=supports)


def observation(value, supports=()):
    return PolicyFacts(models=(PolicySource(Facts, Facts(flag=value), ("facts",)),), supports=supports)


def support(uid, state):
    return PolicySupportFact(uid=uid, state=state)


class PolicyResolverTests(TestCase):
    def resolve(self, spec=None, inputs=None, observations=None, mode=ResolutionMode.VALIDATE_ONLY, **kwargs):
        return PolicyResolver().resolve(spec or admission(), inputs or sources(),
            observations or facts(), mode=mode, **kwargs)

    def test_authored_domain_and_terminal_priority(self):
        for settings, defaults, expected, origin in (
            (Settings(priority=5), Defaults(), 5, PolicyOrigin.AUTHORED),
            (Settings(), Defaults(), 3, PolicyOrigin.DOMAIN_DEFAULT),
            (Settings(), Defaults(priority=None), 0, PolicyOrigin.TERMINAL_DEFAULT),
            (Settings(priority=0), Defaults(), 0, PolicyOrigin.AUTHORED),
            (Settings(), Defaults(priority=0), 0, PolicyOrigin.DOMAIN_DEFAULT),
        ):
            with self.subTest(settings=settings, defaults=defaults):
                decision = self.resolve(inputs=sources(settings, defaults))
                self.assertEqual(decision.effective_priority, expected)
                self.assertEqual(decision.state, PolicyState.DISABLED if expected == 0 else PolicyState.READY)
                self.assertIn(origin, [p.origin for p in decision.provenance])

    def test_disabled_gate_does_not_require_missing_priority_or_support(self):
        only_enabled = PolicyInputs(models=(PolicySource(Settings, Settings(enabled=False), ()),))
        decision = self.resolve(admission((rule(stage=PolicyStage.SUPPORT,
            effect=RequireSupportEffect(("absent",))),)), only_enabled)
        self.assertEqual(decision.state, PolicyState.DISABLED)
        self.assertIsNone(decision.effective_priority)
        self.assertEqual(decision.reasons[0].common_reason, PolicyDisableReason.ENABLED_FALSE)

    def test_invalid_declared_pojo_is_not_hidden_by_disabled(self):
        forged = Settings(enabled=False).model_copy(update={"priority": -2})
        result = self.resolve(inputs=sources(forged))
        self.assertEqual(result.state, PolicyState.UNRESOLVED)
        self.assertEqual(result.issues[0].code, PolicyIssueReason.INVALID_INPUT)

    def test_zero_cannot_be_overridden_and_does_not_wait(self):
        spec = admission((rule(), rule("needs", stage=PolicyStage.SUPPORT, effect=RequireSupportEffect(("parent",)))))
        result = self.resolve(spec, sources(Settings(priority=0)), facts(supports=(support("parent", PolicySupportState.PENDING),)))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertEqual(result.reasons[0].common_reason, PolicyDisableReason.ZERO_PRIORITY)

    def test_unknown_fact_runtime_fallback_preserves_issue(self):
        spec = admission((rule(conditions=(Equal(FLAG, True),)),))
        for mode, expected in ((ResolutionMode.RUNTIME, PolicyState.DISABLED),
                               (ResolutionMode.VALIDATE_ONLY, PolicyState.UNRESOLVED)):
            result = self.resolve(spec, observations=observation(UnknownFact(issue=ERROR)), mode=mode)
            self.assertEqual(result.state, expected)
            self.assertEqual(result.issues, (ERROR,))
            if mode is ResolutionMode.RUNTIME:
                self.assertEqual(result.reasons[-1].common_reason, PolicyDisableReason.ERROR_FALLBACK)
                self.assertEqual(result.provenance[-1].origin, PolicyOrigin.FALLBACK)

    def test_false_dominates_unknown_and_waiting_in_and(self):
        for value in (UnknownFact(issue=ERROR), WaitingFact(support_uids=("parent",))):
            result = self.resolve(admission((rule(conditions=(Equal(FLAG, True), Equal(ENABLED, False))),)),
                                  observations=observation(value))
            self.assertEqual(result.state, PolicyState.READY)
            self.assertIsNone(result.behavior)

    def test_proven_disable_dominates_unneeded_unknown_or_waiting(self):
        for value in (UnknownFact(issue=ERROR), WaitingFact(support_uids=("parent",))):
            for order in permutations((rule("uncertain", conditions=(Equal(FLAG, True),)),
                    rule("forbid", effect=DisableEffect(PolicyDisableReason.POLICY_FORBID)))):
                result = self.resolve(admission(order), observations=observation(value))
                self.assertEqual(result.state, PolicyState.DISABLED)
                self.assertFalse(result.issues)

    def test_precedence_winner_and_equal_conflict_do_not_depend_on_order(self):
        for precedence, state in ((2, PolicyState.READY), (1, PolicyState.UNRESOLVED)):
            for order in permutations((rule("a"), rule("b", precedence=precedence,
                    effect=SelectBehaviorEffect(Action.SECOND)))):
                result = self.resolve(admission(order))
                self.assertEqual(result.state, state)
                if state is PolicyState.READY:
                    self.assertEqual(result.behavior, Action.SECOND)
                else:
                    self.assertEqual(result.issues[0].code, PolicyIssueReason.RULE_CONFLICT)
                    self.assertEqual(tuple(i.path for i in result.issues), (("rules", "a"), ("rules", "b")))

    def test_same_value_equal_precedence_is_not_conflict(self):
        result = self.resolve(admission((rule("a"), rule("b"))))
        self.assertEqual(result.state, PolicyState.READY)
        self.assertEqual(result.behavior, Action.FIRST)

    def test_lower_uncertain_selection_does_not_block_higher_proven(self):
        result = self.resolve(admission((rule("uncertain", conditions=(Equal(FLAG, True),)),
            rule("winner", precedence=2))), observations=observation(UnknownFact(issue=ERROR)))
        self.assertEqual(result.state, PolicyState.READY)

    def test_higher_uncertain_selection_blocks_lower_proven(self):
        result = self.resolve(admission((rule("uncertain", precedence=2, conditions=(Equal(FLAG, True),)),
            rule("lower"))), observations=observation(UnknownFact(issue=ERROR)))
        self.assertEqual(result.state, PolicyState.UNRESOLVED)

    def test_select_default_does_not_override_authored(self):
        spec = admission((rule(stage=PolicyStage.PRIORITY, effect=SelectPriorityDefaultEffect(ALTERNATIVE)),))
        self.assertEqual(self.resolve(spec).effective_priority, 7)
        self.assertEqual(self.resolve(spec, sources(Settings(priority=2))).effective_priority, 2)

    def test_unknown_default_rule_is_not_needed_for_authored_priority(self):
        spec = admission((rule(stage=PolicyStage.PRIORITY, effect=SelectPriorityDefaultEffect(ALTERNATIVE),
            conditions=(Equal(FLAG, True),)),))
        result = self.resolve(spec, sources(Settings(priority=2)), observation(UnknownFact(issue=ERROR)))
        self.assertEqual(result.state, PolicyState.READY)

    def test_priority_sources_conflict_by_value_and_not_field_identity(self):
        spec = admission((rule("a", stage=PolicyStage.PRIORITY, effect=SelectPriorityDefaultEffect(DEFAULT)),
                          rule("b", stage=PolicyStage.PRIORITY, effect=SelectPriorityDefaultEffect(ALTERNATIVE))))
        for rules in permutations(spec.rules):
            # Stable ordering applies across common zero/enabled and domain rules.
            result = self.resolve(replace(spec, rules=rules))
            self.assertEqual(result.state, PolicyState.UNRESOLVED)
            self.assertEqual(result.issues[0].code, PolicyIssueReason.RULE_CONFLICT)
        result = self.resolve(spec, inputs=sources(defaults=Defaults(priority=7)))
        self.assertEqual(result.state, PolicyState.READY)
        self.assertEqual(result.effective_priority, 7)

    def test_priority_proven_disable_beats_unknown_default(self):
        spec = admission((rule("unknown", stage=PolicyStage.PRIORITY,
            effect=SelectPriorityDefaultEffect(ALTERNATIVE), conditions=(Equal(FLAG, True),)),
            rule("disable", stage=PolicyStage.PRIORITY, effect=DisableEffect(PolicyDisableReason.POLICY_FORBID))))
        result = self.resolve(spec, observations=observation(UnknownFact(issue=ERROR)))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertFalse(result.issues)

    def test_all_unknown_condition_diagnostics_are_retained(self):
        missing = DirectValueRef(FieldRef(lambda: Settings, lambda s: s.enabled))
        reader = PolicyReader(PolicyInputs(), observation(UnknownFact(issue=ERROR)))
        result = reader.conditions((Equal(FLAG, True), Equal(missing, True)))
        self.assertEqual(len(result.issues), 2)
        self.assertIn(ERROR, result.issues)

    def test_higher_known_and_unknown_supports_remain_required(self):
        spec = admission((rule("higher", precedence=99), rule("support", stage=PolicyStage.SUPPORT,
            effect=RequireSupportEffect(("parent",)))))
        result = self.resolve(spec, observations=facts(supports=(support("parent", PolicySupportState.PENDING),)))
        self.assertEqual(result.state, PolicyState.WAITING_SUPPORT)
        self.assertIsNone(result.behavior)
        failed = self.resolve(spec, observations=facts(supports=(support("parent", PolicySupportState.FAILED),)),
                              resume=result)
        self.assertEqual(failed.state, PolicyState.UNRESOLVED)

    def test_preview_and_runtime_match_on_valid_inputs(self):
        spec = admission((rule(),))
        self.assertEqual(self.resolve(spec), self.resolve(spec, mode=ResolutionMode.RUNTIME))
        self.assertEqual(self.resolve(spec).reasons[-1].domain_reason, Reason.SELECTED)

    def test_malformed_fact_is_validated_even_when_disabled(self):
        malformed = Facts(flag=KnownFact(value=True)).model_copy(update={"flag": "wrong"})
        result = self.resolve(inputs=sources(Settings(enabled=False)), observations=PolicyFacts(
            models=(PolicySource(Facts, malformed, ("facts",)),)))
        self.assertEqual(result.state, PolicyState.UNRESOLVED)

    def test_required_support_states(self):
        spec = admission((rule(stage=PolicyStage.SUPPORT, effect=RequireSupportEffect(("parent",))),))
        for state, expected in ((PolicySupportState.ACCEPTED, PolicyState.READY),
                (PolicySupportState.PENDING, PolicyState.WAITING_SUPPORT),
                (PolicySupportState.DISABLED, PolicyState.DISABLED),
                (PolicySupportState.MISSING, PolicyState.UNRESOLVED),
                (PolicySupportState.FAILED, PolicyState.UNRESOLVED),
                (PolicySupportState.CYCLE, PolicyState.UNRESOLVED)):
            with self.subTest(state=state):
                result = self.resolve(spec, observations=facts(supports=(support("parent", state),)))
                self.assertEqual(result.state, expected)
                if state is PolicySupportState.DISABLED:
                    self.assertEqual(result.reasons[-1].common_reason, PolicyDisableReason.SUPPORT_DISABLED)
        self.assertEqual(self.resolve(spec).issues[0].code, PolicyIssueReason.MISSING_SUPPORT)

    def test_failed_support_dominates_disabled_and_retains_cause(self):
        spec = admission((rule(stage=PolicyStage.SUPPORT, effect=RequireSupportEffect(("bad", "off"))),))
        result = self.resolve(spec, observations=facts(supports=(support("bad", PolicySupportState.FAILED),
                                                               support("off", PolicySupportState.DISABLED))))
        self.assertEqual(result.state, PolicyState.UNRESOLVED)
        self.assertTrue(result.issues)
        self.assertTrue(any(p.source_path == ("supports", "off") for p in result.provenance))

    def test_resume_only_reads_support_and_behavior(self):
        spec = admission((rule("support", stage=PolicyStage.SUPPORT, effect=RequireSupportEffect(("parent",))), rule()))
        inputs = sources(Settings(priority=8))
        pending = self.resolve(spec, inputs, facts(supports=(support("parent", PolicySupportState.PENDING),)))
        self.assertEqual(pending.state, PolicyState.WAITING_SUPPORT)
        original = PolicyReader.read
        read_models = []
        def tracked(reader, reference):
            read_models.append(reference.bound_field.model)
            return original(reader, reference)
        with patch.object(PolicyReader, "read", tracked):
            ready = self.resolve(spec, inputs, facts(supports=(support("parent", PolicySupportState.ACCEPTED),)), resume=pending)
        self.assertFalse(read_models)
        self.assertEqual(ready.effective_priority, 8)
        self.assertEqual(ready.behavior, Action.FIRST)
        self.assertTrue(all(p in ready.provenance for p in pending.provenance))
        with self.assertRaises(ValueError):
            self.resolve(spec, inputs, facts(), resume=ready)
        with self.assertRaises(ValueError):
            self.resolve(spec, inputs, facts(), resume=pending.model_copy(update={"waiting_supports": ()}))

    def test_independent_domain_value_selection_has_no_priority(self):
        other_rule = PolicyRule[OtherAction, Reason](id=PolicyRuleId("coating"), stage=PolicyStage.BEHAVIOR,
            precedence=RulePrecedence(0), conditions=(), effect=SelectBehaviorEffect(OtherAction.KEEP))
        spec = ValueSelectionPolicySpec[OtherAction, Reason](operation=PolicyOperation.VALUE_SELECTION,
            rules=(other_rule,), expected_behavior_type=OtherAction, fallback_rules=())
        result = self.resolve(spec, PolicyInputs(), PolicyFacts())
        self.assertEqual(result.behavior, OtherAction.KEEP)
        self.assertIsNone(result.effective_priority)
        with self.assertRaises(ValueError):
            self.resolve(spec, resume=self.resolve(admission((rule(stage=PolicyStage.SUPPORT,
                effect=RequireSupportEffect(("parent",))),)), observations=facts(supports=(support("parent", PolicySupportState.PENDING),))))

    def test_no_match_requires_value_and_only_explicit_fallback_applies(self):
        spec = ValueSelectionPolicySpec[Action, Reason](operation=PolicyOperation.VALUE_SELECTION,
            rules=(), expected_behavior_type=Action, fallback_rules=())
        result = self.resolve(spec, mode=ResolutionMode.RUNTIME)
        self.assertEqual(result.state, PolicyState.UNRESOLVED)
        self.assertEqual(result.issues[0].code, PolicyIssueReason.RULE_NO_MATCH)
        fallback = PolicyFallback(reason=PolicyIssueReason.RULE_NO_MATCH, behavior=Action.SECOND, disable_object=True)
        result = self.resolve(replace(spec, fallback_rules=(fallback,)), mode=ResolutionMode.RUNTIME)
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertEqual(result.behavior, Action.SECOND)
        self.assertTrue(result.issues)

    def test_known_none_presence_and_in_set(self):
        spec = admission((rule(conditions=(IsPresent(FLAG), InSet(FLAG, frozenset((True,))))),))
        self.assertEqual(self.resolve(spec, observations=facts(True)).behavior, Action.FIRST)
        self.assertIsNone(self.resolve(spec, observations=facts(None)).behavior)

    def test_missing_model_is_unknown_and_ambiguous_binding_rejected(self):
        result = self.resolve(admission((rule(conditions=(Equal(FLAG, True),)),)), observations=PolicyFacts())
        self.assertEqual(result.state, PolicyState.UNRESOLVED)
        self.assertEqual(result.issues[0].path, ("Facts", "flag"))
        binding = PolicySource(Settings, Settings(), ())
        with self.assertRaises(ValueError):
            PolicyInputs(models=(binding, binding))
        with self.assertRaises(ValueError):
            self.resolve(inputs=PolicyInputs(models=(binding,)), observations=PolicyFacts(models=(binding,)))

    def test_executor_imports_no_domain_providers_or_other_executors(self):
        root = Path(__file__).resolve().parents[3] / "app/application/policy"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for forbidden in ("hydrology", "terrain", "worldData", "application.cascade", "material", "geometry"):
                        self.assertNotIn(forbidden, module)
