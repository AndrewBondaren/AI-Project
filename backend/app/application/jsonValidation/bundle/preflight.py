"""Read-only section checks, using each consumer's real prepare operation."""
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.application.jsonValidation.resolve import (
    ResolveContext, StrictFieldError, UnresolvedModelError, pydantic_issues, reject_unresolved, report_issues,
)
from app.application.jsonValidation.types import ImportIssue, ImportValidationError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.application.templateLibrary.reliefErrors import ReliefValidationError


def validate_rows(data: Any, prepare: Callable[..., Any], *, ctx: ResolveContext, contextual: bool = False) -> None:
    initial_errors = len(ctx.errors)
    if not isinstance(data, list):
        reject_unresolved(ctx, [WireShapeIssue(location=ctx.location, message="expected list",
                                               code=JsonValidationCode.EXPECTED_LIST)])
    for index, row in enumerate(data):
        row_ctx = ctx.child(index)
        issues: list[ImportIssue]
        if not isinstance(row, dict):
            report_issues(row_ctx, [WireShapeIssue(location=row_ctx.location, message="expected object",
                                                   code=JsonValidationCode.EXPECTED_OBJECT)])
            continue
        before_prepare = len(ctx.errors)
        try:
            prepare(row, row_ctx) if contextual else prepare(row)
            continue
        except UnresolvedModelError as exc:
            issues = exc.issues
        except StrictFieldError as exc:
            issues = [exc.issue]
        except ImportValidationError as exc:
            issues = exc.errors
        except ValidationError as exc:
            # The callback exposes a raw row, without a declared model for checked paths.
            issues = pydantic_issues(row_ctx, None, exc)
        except (ReliefValidationError, ValueError) as exc:
            issues = [WireShapeIssue(location=row_ctx.location, message=str(exc),
                                     code=JsonValidationCode.VALIDATION_ERROR)]
        reported = ctx.errors[before_prepare:]
        report_issues(row_ctx, (issue for issue in issues if issue not in reported))

    if len(ctx.errors) > initial_errors:
        raise UnresolvedModelError(ctx.errors[initial_errors:])
