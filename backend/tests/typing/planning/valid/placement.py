"""Positive placement contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2, PlacementOutcomeV2
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision

from tests.typing.planning.valid.policy import PolicyMode, PolicyReasonKind


def valid_placement_lifecycle(batch: PlacementBatchV2, header: PlacementHeader,
    prepared: PreparedPlacementV2, decision: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind],
    reevaluate: SupportReevaluation) -> None:
    assert_type(PlacementAdmissionInput(header=header, decision=decision), PlacementAdmissionInput)
    session = PlacementSession.start(batch, reevaluate_support=reevaluate)
    assert_type(session.ready_for_preparation(), tuple[PlacementHeader, ...])
    session.submit(prepared)
    assert_type(session.step(), PlacementOutcomeV2 | None)
    assert_type(session.finish(), PlacementBatchResultV2)


from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry, BoundaryGeometryResult
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer, PreparedCoastlineBoundary
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.result import ResolvedPlacementV2


def valid_attached_boundary(source: DeclaredCoastline, snapshot: BoundaryWaterSnapshot,
                            admission: PlacementAdmissionInput, input: CoastlineBoundaryInput) -> None:
    assert_type(snapshot.accepted, tuple[ResolvedPlacementV2, ...])
    assert_type(BoundaryGeometry().prepare(source, snapshot), BoundaryGeometryResult)
    prepared = AttachedCoastlinePreparer().prepare_boundary(source, snapshot, admission)
    assert_type(prepared, PreparedCoastlineBoundary)
    assert_type(prepared.prepared, PreparedPlacementV2)
    assert_type(prepared.boundary.parts[0].path, tuple[HydrologyWaypoint, ...])
    assert_type(CoastlineBoundaryPlanner().prepare(input, snapshot, (admission,), snapshot_uid="dependent"), CoastlineBoundaryPlan)
