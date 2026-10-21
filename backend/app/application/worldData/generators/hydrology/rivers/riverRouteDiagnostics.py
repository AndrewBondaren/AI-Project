"""Route typed facts through the shared runtime/import diagnostic sinks."""

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic


def emit_river_diagnostic(ctx: ResolveContext, diagnostic: RiverRouteDiagnostic) -> None:
    issue = FieldPathError(path=("hydrology", "rivers", diagnostic.object_uid),
                           message=diagnostic.model_dump_json(), code=diagnostic.code.value)
    if ctx.validate_only or ctx.mode is ResolveMode.IMPORT:
        report_issues(ctx, (issue,))
    else:
        log_issues((issue,))
