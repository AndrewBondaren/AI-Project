"""Boundary scope binding and ready-source preparation; no placement scheduling."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer, PreparedCoastlineBoundary
from app.dataModel.hydrology.boundaries.attachedCoastline import BoundaryIssueCode, CoastlineBoundaryInput
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class BoundaryPreparationJob[H: HydrologyPlan]:
    def __init__(self, input: CoastlineBoundaryInput, snapshot: BoundaryWaterSnapshot[H],
                 admissions: tuple[PlacementAdmissionInput, ...], *, snapshot_uid: EntityUid) -> None:
        if not isinstance(input, CoastlineBoundaryInput) or not isinstance(snapshot, BoundaryWaterSnapshot):
            raise TypeError("boundary planning requires typed whole-scope input and final snapshot")
        if not isinstance(admissions, tuple) or any(not isinstance(item, PlacementAdmissionInput) for item in admissions):
            raise TypeError("boundary planning requires immutable typed admissions")
        self.input = CoastlineBoundaryInput.model_validate(input, strict=True)
        self.snapshot = type(snapshot).model_validate(snapshot, strict=True)
        self._sources = {source.location_uid: source for source in self.input.sources}
        identities = tuple(item.header.identity.source_uid for item in admissions)
        if (self.input.grid != self.snapshot.grid or self.input.topology != self.snapshot.topology
                or len(set(identities)) != len(identities) or set(identities) != set(self._sources)):
            raise PlanBuildFailure((FieldPathError(("coastline_boundaries",),
                "boundary input/snapshot/admission scope mismatch", code=BoundaryIssueCode.INVALID_INPUT.value),))
        self.batch = PlacementBatchV2(world_uid=self.snapshot.hydrology.ref.key.world_uid,
            snapshot_uid=snapshot_uid, snapshot_revision=self.snapshot.hydrology.ref.output_fingerprint,
            phase=PlacementPhase.DEPENDENT, topology=fine_topology(self.input.topology, self.input.grid.fine_span),
            objects=admissions, accepted=self.snapshot.accepted)

    def prepare(self, admission: PlacementAdmissionInput) -> PreparedCoastlineBoundary:
        source = self._sources[admission.header.identity.source_uid]
        return AttachedCoastlinePreparer().prepare_boundary(source, self.snapshot, admission)
