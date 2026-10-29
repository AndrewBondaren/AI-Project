"""Post-water boundary caller; scheduling and spatial decisions remain common P2."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer
from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.lifecycle.outcomes import causes
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.hydrology.boundaries.attachedCoastline import (
    AttachedCoastline, BoundaryIssueCode, CoastlineBoundaryInput, CoastlineBoundaryPlan,
)
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.result import (
    DisabledPlacement, PlacementIssueCode, PlacementOutcomeV2, ResolvedPlacementV2, UnresolvedPlacementV2,
)
from app.dataModel.policy.policyEnums import PolicyDisableReason
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CoastlineBoundaryPlanner:
    """Consume whole-scope captured evidence/admissions, never requested output tiles."""

    def prepare[H: HydrologyPlan](self, input: CoastlineBoundaryInput, snapshot: BoundaryWaterSnapshot[H],
                admissions: tuple[PlacementAdmissionInput, ...], *, snapshot_uid: EntityUid) -> CoastlineBoundaryPlan:
        if not isinstance(input, CoastlineBoundaryInput) or not isinstance(snapshot, BoundaryWaterSnapshot):
            raise TypeError("boundary planning requires typed whole-scope input and final snapshot")
        if not isinstance(admissions, tuple) or any(not isinstance(item, PlacementAdmissionInput) for item in admissions):
            raise TypeError("boundary planning requires immutable typed admissions")
        input = CoastlineBoundaryInput.model_validate(input, strict=True)
        snapshot = type(snapshot).model_validate(snapshot, strict=True)
        sources = {source.location_uid: source for source in input.sources}
        identities = tuple(item.header.identity.source_uid for item in admissions)
        if (input.grid != snapshot.grid or input.topology != snapshot.topology
                or len(set(identities)) != len(identities) or set(identities) != set(sources)):
            raise PlanBuildFailure((FieldPathError(("coastline_boundaries",),
                "boundary input/snapshot/admission scope mismatch", code=BoundaryIssueCode.INVALID_INPUT.value),))
        session = PlacementSession.start(PlacementBatchV2(world_uid=snapshot.hydrology.ref.key.world_uid,
            snapshot_uid=snapshot_uid, snapshot_revision=snapshot.hydrology.ref.output_fingerprint,
            phase=PlacementPhase.DEPENDENT, topology=fine_topology(input.topology, input.grid.fine_span),
            objects=admissions, accepted=snapshot.accepted))
        metadata: dict[EntityUid, AttachedCoastline] = {}
        issues = [issue for item in admissions for issue in item.decision.issues]
        while True:
            for header in session.ready_for_preparation():
                try:
                    result = AttachedCoastlinePreparer().prepare_boundary(sources[header.identity.source_uid],
                        snapshot, session.objects[header.identity.region_uid])
                    metadata[header.identity.source_uid] = result.boundary
                    session.submit(result.prepared)
                except PlanBuildFailure as failure:
                    issues.extend(failure.issues)
                    session.fail(header.identity, tuple(diagnostic(header, PlacementIssueCode.CONSTRAINT_VIOLATION,
                        issue.message, path=issue.path) for issue in failure.issues))
            if session.step() is None:
                break
        batch = session.finish()
        # Preserve actual source-to-region causes from captured water outcomes.
        # Only references are enriched; policy states, priority and reasons stay intact.
        water = {outcome.identity.source_uid: outcome for outcome in snapshot.water_outcomes}
        outcomes: list[PlacementOutcomeV2] = []
        for outcome in batch.results:
            target_uid = sources[outcome.identity.source_uid].target_source_uid
            target = water.get(target_uid) if target_uid is not None else None
            causal_disable = isinstance(outcome, DisabledPlacement) and any(
                reason.common_reason is PolicyDisableReason.SUPPORT_DISABLED for reason in outcome.decision.reasons)
            if target is not None and isinstance(outcome, (UnresolvedPlacementV2, DisabledPlacement)) and (
                    isinstance(outcome, UnresolvedPlacementV2) or causal_disable):
                references = tuple(sorted(set((*outcome.causes, *causes((target,)))), key=lambda ref: ref.region_uid))
                outcome = type(outcome).model_validate(outcome.model_copy(update={"causes": references}), strict=True)
            outcomes.append(outcome)
        boundaries = tuple(metadata[outcome.identity.source_uid] for outcome in outcomes
                           if isinstance(outcome, ResolvedPlacementV2))
        return CoastlineBoundaryPlan(boundaries=boundaries, outcomes=tuple(outcomes), issues=tuple(issues))
