"""Shared prepared-input placement pass — tz_map_light_bake § Placement P2."""

from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved, resolve_model
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.placement.constraints import check_candidate
from app.application.worldData.placement.dependencies import DependencyQueue
from app.application.worldData.placement.diagnostics import diagnostic, emit_diagnostics
from app.application.worldData.placement.geometry import PlacementGeometry
from app.dataModel.placement import (
    PlacementBatch, PlacementBatchResult, PlacementDiagnostic, PlacementIssueCode,
    PreparedPlacement, ResolvedPlacement, UnresolvedPlacement, WaterPresence,
)


class _PlacementPass:
    def __init__(self, batch: PlacementBatch, geometry: PlacementGeometry) -> None:
        self.batch = batch
        self.geometry = geometry
        self.objects = {obj.intent.identity.region_uid: obj for obj in batch.objects}
        self.placed = {obj.identity.region_uid: obj for obj in batch.accepted}
        self.queue = DependencyQueue(self.objects, set(self.placed))
        self.notices: list[PlacementDiagnostic] = []

    def _preflight(self, obj: PreparedPlacement) -> tuple[PlacementDiagnostic, ...]:
        issues = []
        if obj.coastline is not None and obj.coastline.water_presence == WaterPresence.UNKNOWN:
            issues.append(diagnostic(obj, PlacementIssueCode.UNKNOWN_COASTLINE_WATER,
                                     obj.coastline.reason, path=("coastline", "water_presence")))
        elif obj.effective_specificity is None:
            issues.append(diagnostic(obj, PlacementIssueCode.MISSING_SPECIFICITY,
                                     "auto specificity has no approved prepared value",
                                     path=("intent", "placement_specificity")))
        if obj.coastline is not None and obj.coastline.water_presence == WaterPresence.ABSENT:
            self.notices.append(diagnostic(obj, PlacementIssueCode.COASTLINE_PRIORITY_LOWERED,
                                           f"effective specificity is 0: {obj.coastline.reason}",
                                           path=("coastline", "water_presence")))
        if not obj.candidates:
            issues.append(diagnostic(obj, PlacementIssueCode.NO_CANDIDATES,
                                     "no prepared placement candidates", path=("candidates",)))
        missing = tuple(sorted(self.queue.targets[obj.intent.identity.region_uid] - self.objects.keys() - self.placed.keys()))
        if missing:
            issues.append(diagnostic(obj, PlacementIssueCode.MISSING_DEPENDENCY,
                                     "required placement dependency is absent from snapshot",
                                     path=("dependencies",), related=missing))
        return tuple(issues)

    def _place(self, obj: PreparedPlacement) -> ResolvedPlacement | UnresolvedPlacement:
        failures = []
        for candidate in sorted(obj.candidates, key=lambda item: (item.preference, item.candidate_uid)):
            issues = check_candidate(obj, candidate, self.placed, self.geometry)
            if not issues:
                return ResolvedPlacement(prepared=obj, candidate_uid=candidate.candidate_uid)
            failures.extend(issues)
        return UnresolvedPlacement(prepared=obj, diagnostics=tuple(failures))

    def run(self) -> PlacementBatchResult:
        failures = {}
        for uid in sorted(self.objects):
            issues = self._preflight(self.objects[uid])
            if issues:
                failures[uid] = UnresolvedPlacement(prepared=self.objects[uid], diagnostics=issues)
        self.queue.settle(failures)
        while self.queue.pending:
            uid = self.queue.next_ready()
            if uid is None:
                self.queue.fail_cycles()
                continue
            outcome = self._place(self.objects[uid])
            if isinstance(outcome, ResolvedPlacement):
                self.placed[uid] = outcome
            self.queue.settle({uid: outcome})
        results = tuple(self.queue.outcomes[uid] for uid in sorted(self.objects))
        issues = [*self.notices, *(issue for obj in results if isinstance(obj, UnresolvedPlacement)
                                  for issue in obj.diagnostics)]
        issues.sort(key=lambda item: (item.region_uid, item.code.value, item.path, item.related_uids, item.detail))
        return PlacementBatchResult(world_uid=self.batch.world_uid, snapshot_uid=self.batch.snapshot_uid,
                                    results=results, diagnostics=tuple(issues))


def resolve_placements(batch: PlacementBatch, *, ctx: ResolveContext) -> PlacementBatchResult:
    # Preserve authored presence; shared Pydantic validation also verifies typed
    # copies and topology without introducing another wire or REF-W resolver.
    batch = resolve_model(PlacementBatch, batch.model_dump(exclude_unset=True, warnings=False), ctx=ctx)
    geometry = PlacementGeometry(batch.topology)
    invalid = [FieldPathError(
        path=ctx.path_prefix + ("accepted", obj.identity.region_uid, "footprint"),
        code=PlacementIssueCode.CONSTRAINT_VIOLATION.value,
        message=f"accepted placement {obj.identity.region_uid} has a footprint outside planar topology",
        schema_id=ctx.schema_id,
    ) for obj in sorted(batch.accepted, key=lambda item: item.identity.region_uid)
        if geometry.canonical_cells(obj.footprint) is None]
    if invalid:
        reject_unresolved(ctx, invalid)
    result = _PlacementPass(batch, geometry).run()
    emit_diagnostics(result, ctx)
    return result
