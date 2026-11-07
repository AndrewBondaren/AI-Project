"""Deliver the diagnostics collected by one Hydrology invocation."""
from app.application.jsonValidation.resolve import ResolveContext, log_issues, logger, report_issues
from app.dataModel.hydrology.waterDiagnostics import (
    WaterDiagnosticReport, WaterPlacementRequiredDiagnostic, WaterPlanningDiagnostic, WaterWorldOceanDiagnostic,
    require_water_diagnostic,
)
from app.dataModel.hydrology.waterKindMismatchIssue import WaterKindMismatchIssue
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition


def emit_water_diagnostic(diagnostic: WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic) -> None:
    payload = require_water_diagnostic(diagnostic).model_dump(mode="json", serialize_as_any=False)
    try:
        logger.warning("water diagnostic", extra={"diagnostic": payload})
    except Exception:
        pass  # Logging delivery is best effort.


def report_water_diagnostics(ctx: ResolveContext,
        facts: tuple[WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic, ...]) -> WaterDiagnosticReport:
    facts = tuple(require_water_diagnostic(diagnostic) for diagnostic in facts)
    report = WaterDiagnosticReport(
        ordered=facts,
        blocking=tuple(d for d in facts if d.disposition is PlanDiagnosticDisposition.ERROR),
        continuations=tuple(d for d in facts if d.disposition is PlanDiagnosticDisposition.FALLBACK
                            and not isinstance(d, WaterPlacementRequiredDiagnostic)),
        notices=tuple(d for d in facts if isinstance(d, WaterWorldOceanDiagnostic)),
    )
    for diagnostic in report.ordered:
        if isinstance(diagnostic.issue, WaterKindMismatchIssue):
            if ctx.collect_only or ctx.validate_only:
                report_issues(ctx, [diagnostic.issue])
            else:
                log_issues([diagnostic.issue])
        elif not (ctx.collect_only or ctx.validate_only):
            emit_water_diagnostic(diagnostic)
    return report
