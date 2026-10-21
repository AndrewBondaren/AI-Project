"""One diagnostic per condition/body via the shared runtime/preview sinks."""

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError


def water_issue(ctx: ResolveContext, uid: str, message: str, code: str) -> None:
    facts = [FieldPathError(path=f"hydrology.water.{uid}", message=message, code=code)]
    if ctx.validate_only:
        report_issues(ctx, facts)
    else:
        log_issues(facts)
