"""P1: declaration validation without compilation or policy execution."""

from dataclasses import FrozenInstanceError, replace
from enum import Enum, IntEnum, StrEnum
from math import inf, nan
from unittest import TestCase

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError
from typing import Annotated

from app.dataModel.cascade.cascadeGraph import BoundField
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.declarations.policyDeclaration import (
    AdmissionPolicy, DeclarationDefaults, PolicyOwner, ValuePolicy,
)
from app.dataModel.policy.declarations.policyIdentity import CommonPolicyOwner, RuleIdentity, RuleKind, ValueBranch
from app.dataModel.policy.objectAdmissionPolicyDefinition import PlacementPolicyDefaults
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyIssueReason, PolicyStage, RulePrecedence
from app.dataModel.policy.policyReferences import DirectValueRef, PriorityValueRef
from app.dataModel.policy.policyRules import (
    DisableEffect, Equal, PolicyFallback, RequireSupportEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect,
)


class Action(StrEnum):
    DECLARED = "declared"
    AUTO = "auto"
    DISABLED = "disabled"


class Reason(StrEnum):
    AUTHORED = "authored"


class Foreign(StrEnum):
    DECLARED = "declared"


class Key(StrEnum):
    SELECT = "select"
    DISABLE = "disable"
    SUPPORT = "support"
    PRIORITY = "priority"


class Owner(PolicyOwner):
    pass


class OtherOwner(PolicyOwner):
    pass


class Settings(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    enabled: StrictBool = True
    priority: Specificity | None = None


_ENABLED = DirectValueRef(FieldRef(lambda: Settings, lambda s: s.enabled))
_PRIORITY = PriorityValueRef(FieldRef(lambda: Settings, lambda s: s.priority))
_TERMINAL = PriorityValueRef(FieldRef(lambda: PlacementPolicyDefaults, lambda d: d.placement_specificity))
_POLICY = ValuePolicy[Action, Reason](owner=Owner, behavior_type=Action, reason_type=Reason,
                                    disabled_behavior=Action.DISABLED)
_FALSE = ValueCase[bool, Action, Reason](when=False, behavior=Action.DECLARED, reason=Reason.AUTHORED)
_TRUE = ValueCase[bool, Action, Reason](when=True, behavior=Action.AUTO)
_SELECTION = SelectByValue[bool, Action, Reason](_POLICY, (_FALSE, _TRUE))


def compound(effect=None, **kwargs):
    return PolicyCaseDeclaration[Action, Reason](key=Key.SELECT, conditions=(Equal(_ENABLED, True),),
        effect=effect if effect is not None else SelectBehaviorEffect(Action.DECLARED), **kwargs)


def admission(**kwargs):
    return AdmissionPolicy[Action, Reason](owner=Owner, behavior_type=Action, reason_type=Reason,
        authored_priority_ref=_PRIORITY, domain_priority_ref=_TERMINAL, terminal_priority_ref=_TERMINAL, **kwargs)


class PolicyDeclarationTests(TestCase):
    def test_policy_identity_is_nominal_and_descriptor_is_not_structural(self):
        second = replace(_POLICY)
        self.assertIsNot(second, _POLICY)
        self.assertNotEqual(second, _POLICY)
        self.assertIs(replace(_POLICY, owner=OtherOwner).behavior_type, Action)
        self.assertIs(_SELECTION.policy, _POLICY)
        self.assertEqual(_POLICY.default_precedence, DeclarationDefaults().precedence)
        self.assertFalse(hasattr(_POLICY, "operation"))

    def test_mutability_is_rejected_at_each_declaration_boundary(self):
        for obj, name in ((_POLICY, "owner"), (_FALSE, "when"), (_SELECTION, "cases"),
                          (EnabledFor(_POLICY), "policy"), (compound(), "key")):
            with self.subTest(obj=type(obj)), self.assertRaises(FrozenInstanceError):
                setattr(obj, name, None)
        for kwargs in ({"cases": [compound()]}, {"fallback_rules": []}):
            with self.assertRaises(ValueError):
                replace(_POLICY, **kwargs)
        with self.assertRaises(ValueError):
            replace(_SELECTION, cases=[_FALSE])
        with self.assertRaises(ValueError):
            replace(compound(), conditions=[Equal(_ENABLED, True)])

    def test_owner_and_enum_types_are_explicit(self):
        for owner in (PolicyOwner, Owner(), object, "owner"):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                replace(_POLICY, owner=owner)
        for kwargs in ({"behavior_type": str}, {"reason_type": str}, {"behavior_type": Action.AUTO}):
            with self.assertRaises(ValueError):
                replace(_POLICY, **kwargs)

    def test_default_and_override_precedence_remain_strict(self):
        for invalid in (-1, True, 1.0, "1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                DeclarationDefaults(precedence=invalid)
            for constructor in (lambda: replace(_POLICY, default_precedence=invalid),
                                lambda: replace(_FALSE, precedence=invalid),
                                lambda: compound(precedence=invalid)):
                with self.assertRaises(ValueError):
                    constructor()
        self.assertIsNone(_FALSE.precedence)
        self.assertEqual(replace(_FALSE, precedence=RulePrecedence(2)).precedence, 2)

    def test_foreign_disabled_and_fallback_behavior_are_rejected(self):
        with self.assertRaises(ValueError):
            replace(_POLICY, disabled_behavior=Foreign.DECLARED)
        fallback = PolicyFallback(reason=PolicyIssueReason.UNKNOWN_FACT, behavior=Action.DISABLED, disable_object=True)
        self.assertEqual(replace(_POLICY, fallback_rules=(fallback,)).fallback_rules, (fallback,))
        for fallbacks in ((fallback, fallback), (replace(fallback, behavior=Foreign.DECLARED),), (object(),)):
            with self.subTest(fallbacks=fallbacks), self.assertRaises(ValueError):
                replace(_POLICY, fallback_rules=fallbacks)

    def test_reason_is_not_inferred_from_selected_behavior(self):
        cases = (replace(_FALSE, reason=Reason.AUTHORED), replace(_TRUE, reason=Reason.AUTHORED))
        self.assertEqual(SelectByValue(_POLICY, cases).cases, cases)
        self.assertIsNone(_TRUE.reason)
        with self.assertRaises(ValueError):
            replace(_SELECTION, cases=(replace(_FALSE, reason=Foreign.DECLARED),))
        with self.assertRaises(ValueError):
            replace(_SELECTION, cases=(replace(_FALSE, behavior=Foreign.DECLARED),))

    def test_invalid_selection_collections_and_values_are_rejected(self):
        for cases in ((), (object(),), (_FALSE, _FALSE), (_FALSE, replace(_FALSE, behavior=Action.AUTO))):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                replace(_SELECTION, cases=cases)
        for value in ([], {}, (), frozenset(), inf, -inf, nan, object()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(_FALSE, when=value)
        with self.assertRaises(ValueError):
            replace(_FALSE, behavior="declared")
        with self.assertRaises(ValueError):
            replace(_FALSE, reason="authored")

    def test_enum_members_cannot_hide_mutable_case_data(self):
        class Mutable(Enum):
            VALUE = []
        for constructor in (lambda: ValueBranch(Mutable.VALUE),
                            lambda: replace(_FALSE, behavior=Mutable.VALUE),
                            lambda: replace(_FALSE, reason=Mutable.VALUE),
                            lambda: replace(_POLICY, behavior_type=Mutable),
                            lambda: replace(compound(), key=Mutable.VALUE)):
            with self.assertRaises(ValueError):
                constructor()

    def test_enabled_and_selection_metadata_require_real_descriptors(self):
        self.assertIs(EnabledFor(admission()).policy.owner, Owner)
        for invalid in (None, Action, {}, object()):
            with self.assertRaises(ValueError):
                EnabledFor(invalid)
            with self.assertRaises(ValueError):
                SelectByValue(invalid, (_FALSE,))

    def test_annotations_do_not_add_persisted_fields_or_run_resolver(self):
        class Resolved(BaseModel, frozen=True):
            autoresolve: Annotated[StrictBool, _SELECTION]
        original = Resolved(autoresolve=False)
        self.assertEqual(original.model_dump(), {"autoresolve": False})
        self.assertEqual(Resolved.model_validate_json(original.model_dump_json()), original)
        self.assertIn(_SELECTION, Resolved.model_fields["autoresolve"].metadata)
        self.assertFalse(hasattr(original, "behavior"))

    def test_compound_stage_is_inferred_only_where_unambiguous(self):
        for effect, expected in ((SelectBehaviorEffect(Action.AUTO), PolicyStage.BEHAVIOR),
                                 (RequireSupportEffect(("support",)), PolicyStage.SUPPORT),
                                 (SelectPriorityDefaultEffect(_TERMINAL), PolicyStage.PRIORITY)):
            case = compound(effect)
            self.assertIs(case.effective_stage, expected)
            self.assertIsNone(case.stage)
            for wrong in PolicyStage:
                if wrong is not expected:
                    with self.assertRaises(ValueError):
                        replace(case, stage=wrong)
        for stage in PolicyStage:
            case = compound(DisableEffect(PolicyDisableReason.POLICY_FORBID), stage=stage)
            self.assertIs(case.effective_stage, stage)
        with self.assertRaises(ValueError):
            compound(DisableEffect(PolicyDisableReason.POLICY_FORBID))

    def test_invalid_compound_key_predicates_and_effects_are_rejected(self):
        for kwargs in ({"key": "select"}, {"conditions": (object(),)}, {"effect": object()},
                       {"reason": "authored"}, {"stage": "behavior"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(compound(), **kwargs)

    def test_descriptor_checks_compound_enum_ownership_and_duplicates(self):
        case = compound()
        self.assertEqual(replace(_POLICY, cases=(case,)).cases, (case,))
        for cases in ((case, case), (replace(case, reason=Foreign.DECLARED),),
                      (replace(case, effect=SelectBehaviorEffect(Foreign.DECLARED)),)):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                replace(_POLICY, cases=cases)

    def test_priority_is_only_available_on_admission_policy(self):
        priority = compound(SelectPriorityDefaultEffect(_TERMINAL))
        self.assertEqual(admission(cases=(priority,)).cases, (priority,))
        for case in (priority, compound(DisableEffect(PolicyDisableReason.POLICY_FORBID), stage=PolicyStage.PRIORITY)):
            with self.assertRaises(ValueError):
                replace(_POLICY, cases=(case,))
        for ref_name in ("authored_priority_ref", "domain_priority_ref", "terminal_priority_ref"):
            with self.assertRaises(ValueError):
                replace(admission(), **{ref_name: _ENABLED})


class RuleIdentityComponentsTests(TestCase):
    def test_scalar_branches_have_type_aware_identity(self):
        class Number(IntEnum):
            ONE = 1
        branches = (ValueBranch(None), ValueBranch(False), ValueBranch(0), ValueBranch(0.0),
                    ValueBranch(-0.0), ValueBranch("0"), ValueBranch(Number.ONE), ValueBranch(1),
                    ValueBranch(Action.DECLARED), ValueBranch(Foreign.DECLARED))
        self.assertEqual(len(set(branches)), len(branches))
        self.assertEqual(ValueBranch(Action.AUTO), ValueBranch(Action.AUTO))
        self.assertEqual(hash(ValueBranch(1.25)), hash(ValueBranch(1.25)))

    def test_identity_variants_distinguish_absent_branch_and_explicit_none(self):
        field = BoundField(Settings, "enabled")
        enabled = RuleIdentity(owner=Owner, kind=RuleKind.ENABLED, field=field)
        selected_none = RuleIdentity(owner=Owner, kind=RuleKind.VALUE_CASE, field=field, branch=ValueBranch(None))
        composite = RuleIdentity(owner=Owner, kind=RuleKind.COMPOSITE_CASE, case_key=Key.SELECT)
        zero = RuleIdentity(owner=CommonPolicyOwner, kind=RuleKind.ZERO_PRIORITY)
        self.assertEqual(len({enabled, selected_none, composite, zero}), 4)
        self.assertEqual(enabled, replace(enabled))
        with self.assertRaises(FrozenInstanceError):
            enabled.owner = OtherOwner

    def test_identity_rejects_invalid_kind_owner_and_variant_components(self):
        field = BoundField(Settings, "enabled")
        valid = RuleIdentity(owner=Owner, kind=RuleKind.VALUE_CASE, field=field, branch=ValueBranch(True))
        for kwargs in ({"owner": object}, {"kind": "value_case"}, {"branch": None}, {"field": None},
                       {"case_key": Key.SELECT}, {"branch": True}, {"field": BoundField(Settings, "missing")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(valid, **kwargs)
        for kind in RuleKind:
            if kind is not RuleKind.ZERO_PRIORITY:
                with self.assertRaises(ValueError):
                    RuleIdentity(owner=Owner, kind=kind)
