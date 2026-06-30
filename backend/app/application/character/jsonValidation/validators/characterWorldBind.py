"""SCH-CHARACTER-WORLD-BIND — docs/tz_json_validation.md JV-6."""

from __future__ import annotations

from app.application.character.jsonValidation.types import CharacterValidationContext
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-CHARACTER-WORLD-BIND"


def validate_character_world_bind(ctx: CharacterValidationContext) -> None:
    sheet = ctx.sheet
    expected = ctx.request.expected_world_schema_version
    if not isinstance(sheet, dict) or expected is None:
        return

    bound = sheet.get("world_schema_version")
    if bound is None:
        return
    if not isinstance(bound, str) or not bound:
        ctx.issues.append(error(
            SCHEMA_ID, "world_schema_version", "INVALID_TYPE",
            "world_schema_version must be a non-empty string",
        ))
        return
    if bound != expected:
        ctx.issues.append(error(
            SCHEMA_ID, "world_schema_version", "SCHEMA_VERSION_MISMATCH",
            f"character bound to schema {bound!r}, world is {expected!r}",
        ))
