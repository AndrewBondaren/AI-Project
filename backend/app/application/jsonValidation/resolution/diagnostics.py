"""Request context, issue delivery and unresolved outcomes."""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NoReturn

from pydantic import BaseModel

from app.application.jsonValidation.types import ImportIssue, ResolveReport, validate_import_issues, wire_loc
from app.dataModel.validation.importIssues.wireLocation import WireLocation

# Preserve the existing jsonValidation resolve logging channel.
logger = logging.getLogger("app.application.jsonValidation.resolve")


class ResolveMode(StrEnum):
    RUNTIME = "runtime"
    IMPORT = "import"


@dataclass
class ResolveContext:
    mode: ResolveMode = ResolveMode.RUNTIME
    partial: bool = False
    location: WireLocation = field(default_factory=WireLocation)
    report: ResolveReport = field(default_factory=ResolveReport)
    schema_id: str | None = None
    validate_only: bool = False
    collect_only: bool = False  # Collect facts without logging; independent of validation policy.

    @property
    def errors(self) -> list[ImportIssue]:
        """Blocking issues. Continuations are available separately on the report."""
        return self.report.issues

    @classmethod
    def for_import(cls, *, validate_only: bool = False) -> ResolveContext:
        """The application entry owns the request policy; children inherit it."""
        # IMPORT is the legacy wire interpretation, identical for preview/apply.
        # Only the explicit flag controls the reaction to new-contract facts.
        return cls(mode=ResolveMode.IMPORT, validate_only=validate_only)

    def child(self, segment: str | int) -> ResolveContext:
        return ResolveContext(
            mode=self.mode,
            validate_only=self.validate_only,
            collect_only=self.collect_only,
            partial=self.partial,
            location=self.location.child(segment),
            report=self.report,
            schema_id=self.schema_id,
        )


class StrictFieldError(ValueError):
    def __init__(self, issue: ImportIssue) -> None:
        (self.issue,) = validate_import_issues((issue,))
        loc = ".".join(str(part) for part in wire_loc(self.issue))
        super().__init__(f"{loc}: {self.issue.message}" if loc else self.issue.message)


class UnresolvedModelError(StrictFieldError):
    """No valid POJO exists. Never substitute this outcome with None/default."""

    def __init__(self, issues: Iterable[ImportIssue]) -> None:
        self.issues = list(validate_import_issues(tuple(issues)))
        super().__init__(self.issues[0])


@dataclass(frozen=True)
class ResolveResult:
    value: BaseModel | None
    issues: tuple[ImportIssue, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.value is not None


def log_issues(issues: Iterable[ImportIssue]) -> None:
    """Log-route for structured facts where no request/report ctx exists."""
    for issue in dict.fromkeys(validate_import_issues(tuple(issues))):
        logger.warning("json_validation | WarningError | loc=%s code=%s | %s",
                       wire_loc(issue), issue.code, issue.message)


def report_issues(ctx: ResolveContext, issues: Iterable[ImportIssue]) -> None:
    """Shared policy-resolve reporting for rejecting and diagnostic callers."""
    admitted = tuple(dict.fromkeys(validate_import_issues(tuple(issues))))
    ctx.errors.extend(admitted)
    if not ctx.validate_only and not ctx.collect_only:
        log_issues(admitted)


def reject_unresolved(ctx: ResolveContext, issues: Iterable[ImportIssue]) -> NoReturn:
    """One rejection point for structured facts from wire/domain checks."""
    failure = UnresolvedModelError(issues)
    report_issues(ctx, failure.issues)
    raise failure


def report_unreported_issues(ctx: ResolveContext, issues: Iterable[ImportIssue], *, since: int = 0) -> None:
    """Forward facts that the nested operation did not already deliver to this report."""
    reported = set(ctx.errors[since:])
    report_issues(ctx, (issue for issue in issues if issue not in reported))


def report_continuation(ctx: ResolveContext, issue: ImportIssue, *, same_wire_cause: bool = False) -> None:
    """Record a producer-authorized continuation without changing admission."""
    if ctx.report.record_continuation(issue, same_wire_cause=same_wire_cause):
        if not ctx.validate_only and not ctx.collect_only:
            log_issues([issue])


def _wire_snapshot(raw: Any) -> Any:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    return raw


def _resolved_snapshot(model: BaseModel) -> Any:
    return model.model_dump(mode="json")


def _json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)



def log_resolve_transform(
    label: str,
    wire: Any,
    result: BaseModel,
    ctx: ResolveContext | None,
) -> None:
    """Log original wire JSON vs resolved POJO when they differ."""
    if ctx is not None and ctx.collect_only:
        return
    before = _wire_snapshot(wire if isinstance(wire, dict) else {})
    after = _resolved_snapshot(result)
    before_json = _json_line(before)
    after_json = _json_line(after)
    if before_json == after_json:
        return
    mode = ctx.mode.value if ctx is not None else ResolveMode.RUNTIME.value
    logger.info(
        "json_validation | resolve | label=%s mode=%s | wire=%s | resolved=%s",
        label,
        mode,
        before_json,
        after_json,
    )
