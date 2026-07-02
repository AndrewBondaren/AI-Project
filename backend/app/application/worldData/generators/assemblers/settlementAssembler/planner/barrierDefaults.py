"""Default barrier templates when world has no barrier_template_registry."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation import barrier_templates
from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry


def lookup_barrier_template(
    world: Any,
    system_type: str,
) -> BarrierTemplateEntry | None:
    return barrier_templates(world).entry_for(system_type)
