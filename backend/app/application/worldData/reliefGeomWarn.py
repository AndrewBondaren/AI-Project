"""Shared rejection of invalid relief geometry (legacy function name retained)."""

from __future__ import annotations

from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def warn_template_invalid_geom(
    template: ReliefTemplate,
    *,
    template_uid: str | None = None,
    source_file: str | None = None,
) -> None:
    """Reject invalid L/θ; no geometry repair (E6)."""
    issues = [FieldPathError(("relief_templates", template_uid or template.system_name, where),
                             f"invalid relief geometry: {reason}", code="DOMAIN_GEOMETRY")
              for where, reason in template.invalid_geom_hits()]
    if issues:
        reject_unresolved(ResolveContext(), issues)
