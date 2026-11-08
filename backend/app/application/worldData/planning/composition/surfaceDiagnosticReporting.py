"""Report captured field issues and operational facts from prepared surface plans."""

import logging
from collections.abc import Iterable
from typing import Any

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, report_continuation, report_issues
from app.application.worldData.planning.composition.hydrologyDiagnosticCollector import HydrologyCallback, HydrologyDiagnostic
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition


def report_surface_diagnostics(diagnostics: Iterable[PlanDiagnostic[Any]], *,
                               resolve_ctx: ResolveContext, on_hydrology: HydrologyCallback) -> None:
    def fields() -> Iterable[PlanDiagnostic]:
        for item in dict.fromkeys(diagnostics):
            if isinstance(item, HydrologyDiagnostic):
                on_hydrology(item)
            elif type(item) is PlanDiagnostic:
                yield item
            else:
                raise TypeError(f"unexpected surface planning diagnostic: {type(item).__name__}")

    report_field_diagnostics(fields(), resolve_ctx=resolve_ctx)


def report_field_diagnostics(diagnostics: Iterable[PlanDiagnostic], *, resolve_ctx: ResolveContext) -> None:
    errors = []
    for item in diagnostics:
        issue = item.issue
        if item.disposition is PlanDiagnosticDisposition.ERROR:
            errors.append(issue)
            if issue not in resolve_ctx.errors:
                report_issues(resolve_ctx, (issue,))
        elif item.disposition is PlanDiagnosticDisposition.FALLBACK:
            report_continuation(resolve_ctx, issue)
        elif not resolve_ctx.collect_only:
            logging.getLogger("app.application.worldData.planning.composition.surfacePlanningAssembler").info("surface planning | path=%s code=%s | %s",
                issue.path, issue.code, issue.message)
    if resolve_ctx.validate_only and errors:
        raise UnresolvedModelError(errors)
