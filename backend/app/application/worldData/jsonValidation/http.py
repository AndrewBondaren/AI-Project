"""HTTP mapping for validation results."""

from __future__ import annotations

from app.application.worldData.jsonValidation.types import ValidationIssue, ValidationResult


def format_validation_issues(result: ValidationResult) -> dict:
    """FastAPI 422 detail body for semantic validation failures."""
    errors = [
        {
            "schema_id": issue.schema_id,
            "path": issue.path,
            "code": issue.code,
            "message": issue.message,
            "severity": issue.severity,
        }
        for issue in result.issues
    ]
    return {
        "validation_failed": True,
        "error_count": sum(1 for i in result.issues if i.severity == "error"),
        "warn_count": sum(1 for i in result.issues if i.severity == "warn"),
        "issues": errors,
    }


def issue_dict(issue: ValidationIssue) -> dict:
    return {
        "schema_id": issue.schema_id,
        "path": issue.path,
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
    }
