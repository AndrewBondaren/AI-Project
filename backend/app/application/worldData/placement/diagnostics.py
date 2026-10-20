"""Spatial facts use the existing validation/logging sinks, without wire policy changes."""

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.placement import PlacementBatchResult, PlacementDiagnostic, PlacementIssueCode, PreparedPlacement


def diagnostic(obj: PreparedPlacement, code: PlacementIssueCode, detail: str, *,
               path: tuple[str | int, ...], related: tuple[str, ...] = ()) -> PlacementDiagnostic:
    uid = obj.intent.identity.region_uid
    return PlacementDiagnostic(code=code, region_uid=uid, related_uids=tuple(sorted(set(related))),
                               path=("objects", uid, *path), detail=detail)


def emit_diagnostics(result: PlacementBatchResult, ctx: ResolveContext) -> None:
    issues = [FieldPathError(
        path=ctx.path_prefix + item.path, schema_id=ctx.schema_id, code=item.code.value,
        message=(f"placement | world_uid={result.world_uid} snapshot_uid={result.snapshot_uid} "
                 f"region_uid={item.region_uid} related_uids={item.related_uids}; {item.detail}"),
    ) for item in result.diagnostics]
    # Same nonblocking runtime / author report boundary as regionIdentity.
    # Policy changes only the sink, never the spatial result or candidate set.
    if ctx.validate_only:
        report_issues(ctx, issues)
    else:
        log_issues(issues)
