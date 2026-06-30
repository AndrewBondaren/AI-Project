"""Synthetic bundle for section import (T2) — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.worldData.jsonValidation.types import SectionKey


def build_synthetic_bundle(
    world: dict[str, Any],
    section: SectionKey,
    section_payload: list[Any] | dict[str, Any],
    *,
    extra_sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge DB world row with one section payload for cross-ref validation."""
    bundle: dict[str, Any] = {"world": deepcopy(world)}
    bundle[section.value] = deepcopy(section_payload)
    if extra_sections:
        for key, value in extra_sections.items():
            bundle[key] = deepcopy(value)
    return bundle
