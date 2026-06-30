"""SchemaValidator registry — docs/tz_json_validation.md § SchemaValidator."""

from __future__ import annotations

from typing import Protocol

from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext


class SchemaValidator(Protocol):
    schema_id: str
    sections: frozenset[SectionKey]

    def validate(self, ctx: ValidationContext) -> None:
        """Append issues to ctx.issues. Must not perform I/O."""


class ValidatorRegistry:
    def __init__(self, validators: list[SchemaValidator] | None = None) -> None:
        self._validators: list[SchemaValidator] = list(validators or [])

    def register(self, validator: SchemaValidator) -> None:
        self._validators.append(validator)

    def for_sections(self, keys: frozenset[SectionKey]) -> list[SchemaValidator]:
        out: list[SchemaValidator] = []
        for v in self._validators:
            if not v.sections:
                out.append(v)
            elif keys & v.sections:
                out.append(v)
        return out
