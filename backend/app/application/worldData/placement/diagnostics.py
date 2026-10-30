"""Spatial facts use the existing validation/logging sinks, without wire policy changes."""

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.placement import PlacementBatchResult, PlacementDiagnostic, PlacementIssueCode
from app.dataModel.placement.lifecycle.header import PlacementHeader, PreparedGeometry
from app.dataModel.placement.result import PlacementBatchResultV2


def diagnostic(obj: PreparedGeometry | PlacementHeader, code: PlacementIssueCode, detail: str, *,
               path: tuple[str | int, ...], related: tuple[str, ...] = ()) -> PlacementDiagnostic:
    uid = obj.identity.region_uid if isinstance(obj, PlacementHeader) else obj.intent.identity.region_uid
    return PlacementDiagnostic(code=code, region_uid=uid, related_uids=tuple(sorted(set(related))),
                               path=("objects", uid, *path), detail=detail)


def preparation_diagnostics(header: PlacementHeader, issues: tuple[FieldPathError, ...]) -> tuple[PlacementDiagnostic, ...]:
    """Transport preparation failures through the existing generic placement sink."""
    return tuple(diagnostic(header, PlacementIssueCode.CONSTRAINT_VIOLATION,
        f"{issue.code}: {issue.message}", path=issue.path) for issue in issues)


def emit_diagnostics(result: PlacementBatchResult | PlacementBatchResultV2, ctx: ResolveContext) -> None:
    issues = [FieldPathError(
        path=ctx.path_prefix + item.path, schema_id=ctx.schema_id, code=item.code.value,
        message=(f"placement | world_uid={result.world_uid} snapshot_uid={result.snapshot_uid} "
                 f"region_uid={item.region_uid} related_uids={item.related_uids}; {item.detail}"),
    ) for item in result.diagnostics]
    # Same nonblocking runtime / author report boundary as regionIdentity.
    # Policy changes only the sink, never the spatial result or candidate set.
    if ctx.validate_only or ctx.collect_only:
        report_issues(ctx, issues)
    else:
        log_issues(issues)
