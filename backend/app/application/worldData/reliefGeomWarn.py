"""Import/library WARN for invalid relief geom knobs (C31) — not reject."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_INVALID_GEOM,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_warning
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def warn_template_invalid_geom(
    template: ReliefTemplate,
    *,
    template_uid: str | None = None,
    source_file: str | None = None,
) -> None:
    """Log each invalid L/θ site; generate still applies 20° fallback."""
    for where, reason in template.invalid_geom_hits():
        relief_warning(
            EVENT_INVALID_GEOM,
            why=reason,
            where=where,
            system_name=template.system_name,
            template_uid=template_uid,
            source_file=source_file,
        )
