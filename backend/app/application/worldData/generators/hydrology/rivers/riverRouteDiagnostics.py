"""Route typed facts through the shared runtime/import diagnostic sinks."""

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic


def is_runtime_river_context(ctx: ResolveContext) -> bool:
    return ctx.mode is ResolveMode.RUNTIME and not ctx.validate_only


def emit_river_diagnostic(ctx: ResolveContext, diagnostic: RiverRouteDiagnostic) -> None:
    issue = FieldPathError(path=("hydrology", "rivers", diagnostic.object_uid),
                           message=diagnostic.model_dump_json(), code=diagnostic.code.value)
    if ctx.collect_only or not is_runtime_river_context(ctx):
        report_issues(ctx, (issue,))
    else:
        log_issues((issue,))
