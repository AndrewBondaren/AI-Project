"""Terminal admission outcomes and causal dependency aggregation."""

from enum import Enum

from app.application.worldData.placement.diagnostics import diagnostic
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.causal import PlacementOutcomeRef, PlacementOutcomeStatus
from app.dataModel.placement.result import DisabledPlacement, PlacementIssueCode, PlacementOutcomeV2, UnresolvedPlacementV2
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyReason
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyState


def causes(outcomes: tuple[PlacementOutcomeV2, ...], missing: tuple[str, ...] = ()) -> tuple[PlacementOutcomeRef, ...]:
    refs = [PlacementOutcomeRef(region_uid=o.identity.region_uid, status=PlacementOutcomeStatus(o.status)) for o in outcomes]
    refs.extend(PlacementOutcomeRef(region_uid=uid, status=PlacementOutcomeStatus.UNRESOLVED) for uid in missing)
    return tuple(sorted(refs, key=lambda r: r.region_uid))


def admission_outcome(obj: PlacementAdmissionInput) -> DisabledPlacement | UnresolvedPlacementV2 | None:
    decision = obj.decision
    if decision.state is PolicyState.DISABLED:
        if not decision.reasons:
            raise ValueError("disabled admission requires explicit reason")
        reason = decision.reasons[-1].common_reason
        diagnostics = tuple(diagnostic(obj.header, PlacementIssueCode.CONSTRAINT_VIOLATION,
            i.message, path=("policy", *i.path)) for i in decision.issues)
        return DisabledPlacement(identity=obj.header.identity, reason=reason, decision=decision, diagnostics=diagnostics)
    if decision.state is PolicyState.UNRESOLVED:
        issues = tuple(diagnostic(obj.header, PlacementIssueCode.CONSTRAINT_VIOLATION,
                                 i.message, path=("policy", *i.path)) for i in decision.issues)
        return UnresolvedPlacementV2(identity=obj.header.identity, prepared=None, diagnostics=issues)
    return None


def dependency_outcome(obj: PlacementAdmissionInput, outcomes: tuple[PlacementOutcomeV2, ...], *,
                       missing: tuple[str, ...] = ()) -> DisabledPlacement | UnresolvedPlacementV2 | None:
    failed = tuple(o.identity.region_uid for o in outcomes if isinstance(o, UnresolvedPlacementV2))
    disabled = tuple(o.identity.region_uid for o in outcomes if isinstance(o, DisabledPlacement))
    refs = causes(outcomes, missing)
    if failed or missing:
        issues = []
        if missing:
            issues.append(diagnostic(obj.header, PlacementIssueCode.MISSING_DEPENDENCY,
                "required dependency is absent from snapshot", path=("dependencies",), related=missing))
        if failed:
            issues.append(diagnostic(obj.header, PlacementIssueCode.FAILED_DEPENDENCY,
                "required dependency is unresolved", path=("dependencies",), related=failed))
        return UnresolvedPlacementV2(identity=obj.header.identity, prepared=None, diagnostics=tuple(issues), causes=refs)
    if disabled:
        reason = PolicyReason[Enum](domain_reason=None, common_reason=PolicyDisableReason.SUPPORT_DISABLED)
        decision = ObjectAdmissionDecision[Enum, Enum](operation=obj.decision.operation,
            state=PolicyState.DISABLED, effective_priority=obj.decision.effective_priority, behavior=None,
            reasons=obj.decision.reasons + (reason,), waiting_supports=(),
            provenance=obj.decision.provenance, issues=())
        return DisabledPlacement(identity=obj.header.identity, reason=PolicyDisableReason.SUPPORT_DISABLED,
                                 decision=decision, causes=refs)
    return None
