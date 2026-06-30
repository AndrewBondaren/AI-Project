"""Validation issue helpers."""

from __future__ import annotations

from app.application.worldData.jsonValidation.types import ValidationIssue


def error(
    schema_id: str,
    path: str,
    code: str,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(
        schema_id=schema_id,
        path=path,
        code=code,
        message=message,
        severity="error",
    )
