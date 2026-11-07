"""Stable surface TLV registrations for app.dataModel.policy."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.policy.objectAdmissionPolicyDefinition import ObjectAdmissionFacts, PlacementPolicyDefaults
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyProvenance, PolicyReason
from app.dataModel.policy.policyEnums import (
    FactState,
    PolicyDisableReason,
    PolicyIssueReason,
    PolicyOperation,
    PolicyOrigin,
    PolicyStage,
    PolicyState,
)
from app.dataModel.policy.policyFacts import UnknownFact, WaitingFact
from app.dataModel.policy.policyTypeError import (
    PolicyModelIssue,
    PolicyRuleIssue,
    PolicySupportIssue,
    PolicyTypeError,
)
from enum import Enum


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (213, UnknownFact, CanonicalTypeKind.RECORD),
    (214, WaitingFact, CanonicalTypeKind.RECORD),
    (215, FactState, CanonicalTypeKind.ENUM),
    (218, PolicyProvenance, CanonicalTypeKind.RECORD),
    (219, PolicyOperation, CanonicalTypeKind.ENUM),
    (220, PolicyState, CanonicalTypeKind.ENUM),
    (221, PolicyDisableReason, CanonicalTypeKind.ENUM),
    (222, PolicyOrigin, CanonicalTypeKind.ENUM),
    (264, ObjectAdmissionDecision[Enum, Enum], CanonicalTypeKind.RECORD),
    (265, PolicyReason[Enum], CanonicalTypeKind.RECORD),
    (298, PolicyRuleIssue, CanonicalTypeKind.RECORD),
    (299, PolicySupportIssue, CanonicalTypeKind.RECORD),
    (300, PolicyModelIssue, CanonicalTypeKind.RECORD),
    (301, PolicyTypeError, CanonicalTypeKind.RECORD),
    (309, PolicyIssueReason, CanonicalTypeKind.ENUM),
    (310, PolicyStage, CanonicalTypeKind.ENUM),
    (312, ObjectAdmissionFacts, CanonicalTypeKind.RECORD),
    (313, PlacementPolicyDefaults, CanonicalTypeKind.RECORD),
)
