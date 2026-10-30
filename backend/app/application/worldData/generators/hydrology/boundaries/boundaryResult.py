"""Hydrology boundary result assembly and target-water causal attribution."""

from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.lifecycle.outcomes import causes
from app.dataModel.hydrology.boundaries.attachedCoastline import AttachedCoastline, CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.result import (
    DisabledPlacement, PlacementBatchResultV2, PlacementDiagnostic, PlacementIssueCode, PlacementOutcomeV2,
    ResolvedPlacementV2, UnresolvedPlacementV2,
)
from app.dataModel.policy.policyEnums import PolicyDisableReason
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class BoundaryResultAssembler[H: HydrologyPlan]:
    def __init__(self, input: CoastlineBoundaryInput, snapshot: BoundaryWaterSnapshot[H], batch: PlacementBatchV2) -> None:
        self._sources = {source.location_uid: source for source in input.sources}
        self._water = {outcome.identity.source_uid: outcome for outcome in snapshot.water_outcomes}
        self._metadata: dict[EntityUid, AttachedCoastline] = {}
        self._issues = [issue for item in batch.objects for issue in item.decision.issues]

    def record(self, boundary: AttachedCoastline) -> None:
        self._metadata[boundary.source_uid] = boundary

    def record_failure(self, header: PlacementHeader, issues: tuple[FieldPathError, ...]) -> tuple[PlacementDiagnostic, ...]:
        self._issues.extend(issues)
        return tuple(diagnostic(header, PlacementIssueCode.CONSTRAINT_VIOLATION,
            issue.message, path=issue.path) for issue in issues)

    def assemble(self, batch: PlacementBatchResultV2) -> CoastlineBoundaryPlan:
        outcomes = tuple(self._with_water_causes(outcome) for outcome in batch.results)
        boundaries = tuple(self._metadata[outcome.identity.source_uid] for outcome in outcomes
                           if isinstance(outcome, ResolvedPlacementV2))
        return CoastlineBoundaryPlan(boundaries=boundaries, outcomes=outcomes, issues=tuple(self._issues))

    def _with_water_causes(self, outcome: PlacementOutcomeV2) -> PlacementOutcomeV2:
        target_uid = self._sources[outcome.identity.source_uid].target_source_uid
        target = self._water.get(target_uid) if target_uid is not None else None
        causal_disable = isinstance(outcome, DisabledPlacement) and any(
            reason.common_reason is PolicyDisableReason.SUPPORT_DISABLED for reason in outcome.decision.reasons)
        if target is not None and isinstance(outcome, (UnresolvedPlacementV2, DisabledPlacement)) and (
                isinstance(outcome, UnresolvedPlacementV2) or causal_disable):
            references = tuple(sorted(set((*outcome.causes, *causes((target,)))), key=lambda ref: ref.region_uid))
            return type(outcome).model_validate(outcome.model_copy(update={"causes": references}), strict=True)
        return outcome
