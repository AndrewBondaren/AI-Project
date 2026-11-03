"""Submit one offered competitor against its frozen fine-placement inputs."""

from collections.abc import Callable

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import CapturedPlacementGeometry, PreparedPlacementV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


def submit_captured_competitor(*, session: PlacementSession, header: PlacementHeader,
        captured: CapturedPlacementGeometry, before: PlanEnvelope[FineSurfaceWindow], expected_before: PlanRef,
        prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2], control: PlanBuildControl) -> None:
    """The caller admits the batch/W/regions graph once before opening this session."""
    control.raise_if_shutdown()
    captured = CapturedPlacementGeometry.model_validate(captured, strict=True)
    batch = session.batch
    if before.ref != expected_before or captured.pre_hydrology_ref != expected_before:
        raise ValueError("competitor requires the exact expected pre-water revision")
    if (batch.phase is not PlacementPhase.PRE_RELIEF or batch.world_uid != expected_before.key.world_uid
            or batch.snapshot_revision != expected_before.output_fingerprint or batch.topology != before.payload.topology):
        raise ValueError("competitor session must use the admitted pre-relief frame and revision")

    uid = header.identity.region_uid
    if uid not in session.offered:
        raise ValueError("competitor requires an offered ready header")
    admission = session.objects[uid]
    if header != admission.header or PlacementHeader.from_intent(captured.intent) != header:
        raise ValueError("captured intent must match the offered placement header")
    for candidate in captured.candidates:
        for cell in candidate.footprint.cells:
            control.raise_if_shutdown()
            if before.payload.topology.canonicalize(*cell) != cell:
                raise ValueError("competitor footprint requires canonical fine coordinates")

    prepared = PreparedPlacementV2.model_validate(prepare_competitor(admission), strict=True)
    if (prepared.intent != captured.intent or prepared.original_area != captured.original_area
            or prepared.candidates != captured.candidates):
        raise ValueError("competitor preparation changed captured geometry")
    control.raise_if_shutdown()
    session.submit(prepared)
