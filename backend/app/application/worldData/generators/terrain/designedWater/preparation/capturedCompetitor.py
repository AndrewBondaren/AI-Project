"""Admit frozen competitor geometry before starting and submitting to native P2."""

from collections.abc import Callable, Mapping
from types import MappingProxyType

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.designedWater.preparation.designUniverse import water_intents_by_region
from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import CapturedPlacementGeometry, PreparedPlacementV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.validation.immutableValue import validate_immutable


def _require_frame(batch: PlacementBatchV2, before: PlanEnvelope[FineSurfaceWindow], expected_before: PlanRef) -> None:
    if before.ref != expected_before:
        raise ValueError("competitor requires the exact expected pre-water revision")
    if (batch.phase is not PlacementPhase.PRE_RELIEF or batch.world_uid != expected_before.key.world_uid
            or batch.snapshot_revision != expected_before.output_fingerprint or batch.topology != before.payload.topology):
        raise ValueError("competitor session must use the admitted pre-relief frame and revision")


def _require_capture_binding(captured: CapturedPlacementGeometry, header: PlacementHeader,
                             before: PlanEnvelope[FineSurfaceWindow], control: PlanBuildControl) -> None:
    if captured.pre_hydrology_ref != before.ref:
        raise ValueError("competitor requires the exact expected pre-water revision")
    if PlacementHeader.from_intent(captured.intent) != header:
        raise ValueError("captured intent must match the offered placement header")
    for candidate in captured.candidates:
        for cell in candidate.footprint.cells:
            control.raise_if_shutdown()
            if before.payload.topology.canonicalize(*cell) != cell:
                raise ValueError("competitor footprint requires canonical fine coordinates")


def start_native_placement_session(*, batch: PlacementBatchV2, before: PlanEnvelope[FineSurfaceWindow],
        expected_before: PlanRef, water_intents: tuple[PlacementIntent, ...],
        competitor_geometry: tuple[CapturedPlacementGeometry, ...], reevaluate_support: SupportReevaluation | None,
        control: PlanBuildControl) -> tuple[PlacementSession, Mapping[EntityUid, CapturedPlacementGeometry]]:
    """Start only after admitting the whole roster. The caller binds W and regions via I5.1."""
    control.raise_if_shutdown()
    batch = PlacementBatchV2.model_validate(batch, strict=True)
    _require_frame(batch, before, expected_before)
    admissions = {item.header.identity.region_uid: item for item in batch.objects}
    water = water_intents_by_region(water_intents, admissions)
    required = {uid for uid, item in admissions.items() if uid not in water
                and item.decision.state in (PolicyState.READY, PolicyState.WAITING_SUPPORT)}
    if type(competitor_geometry) is not tuple:
        raise ValueError("competitor geometry must be an immutable tuple")
    by_region = {}
    previous = None
    for record in competitor_geometry:
        control.raise_if_shutdown()
        if type(record) is not CapturedPlacementGeometry:
            raise ValueError("competitor geometry requires typed capture records")
        validate_immutable(record)
        record = CapturedPlacementGeometry.model_validate(record, strict=True)
        uid = record.intent.identity.region_uid
        if previous is not None and uid <= previous:
            raise ValueError("competitor geometry must have sorted unique region UIDs")
        if uid not in admissions or uid in water:
            raise ValueError("competitor geometry requires a non-water batch header")
        _require_capture_binding(record, admissions[uid].header, before, control)
        by_region[uid] = record
        previous = uid
    missing = required.difference(by_region)
    if missing:
        raise ValueError(f"missing competitor geometry for {sorted(missing)}")
    control.raise_if_shutdown()
    return PlacementSession.start(batch, reevaluate_support=reevaluate_support), MappingProxyType(by_region)


def submit_captured_competitor(*, session: PlacementSession, header: PlacementHeader,
        captured: CapturedPlacementGeometry, before: PlanEnvelope[FineSurfaceWindow], expected_before: PlanRef,
        prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2], control: PlanBuildControl) -> None:
    """The caller admits the batch/W/regions graph once before opening this session."""
    control.raise_if_shutdown()
    _require_frame(session.batch, before, expected_before)
    uid = header.identity.region_uid
    if uid not in session.offered:
        raise ValueError("competitor requires an offered ready header")
    admission = session.objects[uid]
    if header != admission.header:
        raise ValueError("captured intent must match the offered placement header")
    captured = CapturedPlacementGeometry.model_validate(captured, strict=True)
    _require_capture_binding(captured, header, before, control)

    prepared = prepare_competitor(admission)
    if not isinstance(prepared, PreparedPlacementV2):
        raise ValueError("competitor callback must return PreparedPlacementV2")
    # Compare the raw number: strict float validation can round an integer.
    if type(prepared.original_area) not in (int, float) or prepared.original_area != captured.original_area:
        raise ValueError("competitor preparation changed captured original area")
    prepared = PreparedPlacementV2.model_validate(prepared, strict=True)
    if prepared.intent != captured.intent or prepared.candidates != captured.candidates:
        raise ValueError("competitor preparation changed captured geometry")
    control.raise_if_shutdown()
    session.submit(prepared)
