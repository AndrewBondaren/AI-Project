"""Read-only section checks, using each consumer's real prepare operation."""
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved, UnresolvedModelError
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.reliefErrors import ReliefValidationError


def validate_rows(data: Any, prepare: Callable[..., Any], *, ctx: ResolveContext, contextual: bool = False) -> None:
    initial_errors = len(ctx.errors)
    issues: list[FieldPathError] = []
    if not isinstance(data, list):
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "expected list", code="EXPECTED_LIST")])
    for index, row in enumerate(data):
        path = ctx.path_prefix + (index,)
        if not isinstance(row, dict):
            issues.append(FieldPathError(path, "expected object", code="EXPECTED_OBJECT"))
            continue
        try:
            prepare(row, ctx.child(index)) if contextual else prepare(row)
        except UnresolvedModelError as exc:
            # Context-aware consumers already wrote into this report. Legacy
            # consumers may own another context; retain those facts as well.
            issues.extend(issue for issue in exc.issues if issue not in ctx.errors)
        except ValidationError as exc:
            issues.extend(FieldPathError(path + tuple(e["loc"]), e["msg"], code=e["type"])
                          for e in exc.errors())
        except (ValueError, ReliefValidationError) as exc:
            issues.append(FieldPathError(path, str(exc), code="VALIDATION_ERROR"))
    if issues:
        reject_unresolved(ctx, issues)

    if len(ctx.errors) > initial_errors:
        raise UnresolvedModelError(ctx.errors[initial_errors:])
