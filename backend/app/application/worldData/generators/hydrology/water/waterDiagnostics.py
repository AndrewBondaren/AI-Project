"""Emit the producer's explicit disposition without interpreting its issue code."""

from collections.abc import Callable

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition


def water_issue(ctx: ResolveContext, uid: str, message: str, code: str, *,
                disposition: PlanDiagnosticDisposition,
                emit: Callable[[PlanDiagnostic], None] | None = None) -> None:
    issue = FieldPathError(path=("hydrology", "water", uid), message=message, code=code)
    if emit is not None:
        emit(PlanDiagnostic(issue=issue, disposition=disposition))
        return
    facts = [issue]
    if ctx.validate_only or ctx.collect_only:
        report_issues(ctx, facts)
    else:
        log_issues(facts)
