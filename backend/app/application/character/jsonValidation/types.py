"""Character validation types — docs/tz_json_validation.md JV-6."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.worldData.jsonValidation.index.seedRegistryIndex import SeedRegistryIndex
from app.application.worldData.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.worldData.jsonValidation.types import ValidationRequest, ValidationIssue


@dataclass
class CharacterValidationContext:
    request: ValidationRequest
    sheet: dict[str, Any] | None = None
    index: WorldRegistryIndex | None = None
    seed_index: SeedRegistryIndex | None = None
    stat_schema: dict[str, dict[str, Any]] | None = None
    race_uids: frozenset[str] = frozenset()
    location_uids: frozenset[str] = frozenset()
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
