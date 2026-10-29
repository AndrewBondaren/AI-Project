"""Bind ready boundary admission to the domain geometry result and common P2."""

from dataclasses import dataclass

from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry, boundary_failure
from app.dataModel.hydrology.boundaries.attachedCoastline import AttachedCoastline, BoundaryIssueCode
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.placement.common import DependencyRelation, OverlapRelation, PlacementMode
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PlacementCandidate, PlacementFootprint, PreparedPlacementV2
from app.dataModel.policy.policyEnums import PolicyState


@dataclass(frozen=True)
class PreparedCoastlineBoundary:
    """Existing common prepared placement plus domain metadata, not a new transport."""

    prepared: PreparedPlacementV2
    boundary: AttachedCoastline


class AttachedCoastlinePreparer:
    """Structural join only; BoundaryGeometry owns all raster/association work."""

    def prepare_boundary(self, source: DeclaredCoastline, accepted_water: BoundaryWaterSnapshot,
                         admission: PlacementAdmissionInput) -> PreparedCoastlineBoundary:
        if not isinstance(source, DeclaredCoastline) or not isinstance(accepted_water, BoundaryWaterSnapshot):
            raise TypeError("boundary preparation requires typed source and captured water snapshot")
        if not isinstance(admission, PlacementAdmissionInput):
            raise TypeError("boundary preparation requires common typed admission")
        source = DeclaredCoastline.model_validate(source.model_dump(warnings=False), strict=True)
        snapshot = BoundaryWaterSnapshot.model_validate(accepted_water, strict=True)
        admission = PlacementAdmissionInput.model_validate(admission, strict=True)
        header = admission.header
        if source.purpose is not CoastlinePurpose.BODY_BOUNDARY or source.target_source_uid is None:
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "only BODY_BOUNDARY can use attached preparation")
        if admission.decision.state is not PolicyState.READY:
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "boundary geometry requires ready admission")
        if (header.identity.source_uid != source.location_uid or header.mode is not PlacementMode.ABSOLUTE
                or header.identity.world_uid != snapshot.hydrology.ref.key.world_uid):
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "boundary header source/world/absolute mode mismatch")
        target = next((target for target in snapshot.accepted if target.identity.source_uid == source.target_source_uid), None)
        if target is None:
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "explicit target source has no accepted placement")
        target_region = target.identity.region_uid
        if not any(rule.target_uid == target_region and rule.relation is DependencyRelation.CONNECTED_TO for rule in header.dependencies):
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "boundary requires CONNECTED_TO accepted target region")
        if not any(rule.target_uid == target_region and rule.relation is OverlapRelation.SHARED_BOUNDARY for rule in header.permitted_overlaps):
            raise boundary_failure(source, BoundaryIssueCode.INVALID_INPUT, "boundary requires explicit SHARED_BOUNDARY overlap")
        geometry = BoundaryGeometry().prepare(source, snapshot)
        intent = PlacementIntent(identity=header.identity, mode=header.mode, shape=None,
            placement_specificity=source.placement_specificity, dependencies=header.dependencies,
            permitted_overlaps=header.permitted_overlaps, separations=header.separations)
        prepared = PreparedPlacementV2(intent=intent, original_area=float(len(geometry.cells)),
            candidates=(PlacementCandidate(candidate_uid=source.location_uid, preference=0,
                footprint=PlacementFootprint(cells=geometry.cells, z_min=None, z_max=None)),),
            decision=admission.decision)
        return PreparedCoastlineBoundary(prepared=prepared, boundary=geometry.boundary)
