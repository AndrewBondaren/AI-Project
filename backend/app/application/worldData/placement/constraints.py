"""Domain-neutral dependency predicates and pair constraints, for one prepared variant."""

from collections.abc import Mapping

from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.geometry import PlacementGeometry
from app.dataModel.placement import (
    DependencyRelation, OverlapRelation, PlacementCandidate, PlacementDiagnostic, PlacementIssueCode,
    PreparedPlacement, ResolvedPlacement,
)


def _dependency_satisfied(relation: DependencyRelation, candidate: PlacementCandidate,
                          target: ResolvedPlacement, geometry: PlacementGeometry) -> bool:
    match relation:
        case DependencyRelation.RESOLVED:
            return True
        case DependencyRelation.CONTAINED_BY:
            return geometry.contains(target.footprint, candidate.footprint)
        case DependencyRelation.SUPPORTED_BY:
            return geometry.supports(target.footprint, candidate.footprint)
        case DependencyRelation.CONNECTED_TO:
            return geometry.connected(target.footprint, candidate.footprint)
    raise ValueError(f"unsupported dependency relation: {relation}")


def _overlap_permitted(obj: PreparedPlacement, candidate: PlacementCandidate,
                       target: ResolvedPlacement, geometry: PlacementGeometry) -> bool:
    uid, target_uid = obj.intent.identity.region_uid, target.identity.region_uid
    relations = {rule.relation for rule in obj.intent.permitted_overlaps if rule.target_uid == target_uid}
    relations.update(rule.relation for rule in target.prepared.intent.permitted_overlaps if rule.target_uid == uid)
    for relation in relations:
        match relation:
            case OverlapRelation.COVERAGE:
                return True
            case OverlapRelation.CONTAINMENT | OverlapRelation.EMBEDDING:
                if (geometry.contains(target.footprint, candidate.footprint)
                        or geometry.contains(candidate.footprint, target.footprint)):
                    return True
            case OverlapRelation.CONNECTION | OverlapRelation.SHARED_BOUNDARY:
                if geometry.shared_boundary(candidate.footprint, target.footprint):
                    return True
    return False


def check_candidate(obj: PreparedPlacement, candidate: PlacementCandidate,
                    placed: Mapping[str, ResolvedPlacement], geometry: PlacementGeometry) -> tuple[PlacementDiagnostic, ...]:
    path = ("candidates", candidate.candidate_uid, "footprint")
    if geometry.canonical_cells(candidate.footprint) is None:
        return (diagnostic(obj, PlacementIssueCode.CONSTRAINT_VIOLATION,
                           f"candidate {candidate.candidate_uid}: footprint extends outside planar world bounds",
                           path=path),)
    issues = []
    for dependency in sorted(obj.intent.dependencies, key=lambda rule: (rule.target_uid, rule.relation.value)):
        target = placed[dependency.target_uid]  # Queue guarantees that required supports are resolved.
        if not _dependency_satisfied(dependency.relation, candidate, target, geometry):
            issues.append(diagnostic(
                obj, PlacementIssueCode.CONSTRAINT_VIOLATION,
                f"candidate {candidate.candidate_uid}: {dependency.relation.value} predicate failed",
                path=path, related=(dependency.target_uid,)))
    if issues:
        return tuple(issues)

    uid = obj.intent.identity.region_uid
    for target_uid in sorted(placed):
        target = placed[target_uid]
        reserves = [(uid, rule) for rule in obj.intent.separations if rule.target_uid == target_uid]
        reserves.extend((target_uid, rule) for rule in target.prepared.intent.separations if rule.target_uid == uid)
        reserve_failed = False
        for owner, rule in reserves:
            if not geometry.separated(candidate.footprint, target.footprint, min_xy=rule.min_xy, min_z=rule.min_z):
                reserve_failed = True
                issues.append(diagnostic(
                    obj, PlacementIssueCode.CONSTRAINT_VIOLATION,
                    f"candidate {candidate.candidate_uid}: separation of {owner} failed "
                    f"(min_xy={rule.min_xy}, min_z={rule.min_z})",
                    path=path, related=(target_uid,)))
        if (not reserve_failed and geometry.collides(candidate.footprint, target.footprint)
                and not _overlap_permitted(obj, candidate, target, geometry)):
            issues.append(diagnostic(obj, PlacementIssueCode.SPATIAL_CONFLICT,
                                     f"candidate {candidate.candidate_uid}: exclusive footprint conflict",
                                     path=path, related=(target_uid,)))
    return tuple(issues)
