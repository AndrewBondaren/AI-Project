"""SCH-CHARACTER-ROW — docs/tz_json_validation.md JV-6."""

from __future__ import annotations

import dataclasses
from typing import Any

from app.application.character.jsonValidation.types import CharacterValidationContext
from app.application.worldData.jsonValidation.validators._issues import error
from app.db.models.player import Player

SCHEMA_ID = "SCH-CHARACTER-ROW"

_PLAYER_FIELDS = frozenset(f.name for f in dataclasses.fields(Player))
_AUTO_FIELDS = frozenset({"character_uid", "created_at"})


def validate_character_row(ctx: CharacterValidationContext) -> None:
    sheet = ctx.sheet
    if not isinstance(sheet, dict):
        ctx.issues.append(error(SCHEMA_ID, "$", "INVALID_TYPE", "character sheet must be an object"))
        return

    if not isinstance(sheet.get("display_name"), str) or not sheet.get("display_name"):
        ctx.issues.append(error(
            SCHEMA_ID, "display_name", "MISSING_FIELD", "display_name is required",
        ))

    for key in sheet:
        if key not in _PLAYER_FIELDS:
            ctx.issues.append(error(
                SCHEMA_ID, key, "UNKNOWN_FIELD", f"unknown character field {key!r}",
            ))

    for field in _AUTO_FIELDS:
        if field in sheet:
            ctx.issues.append(error(
                SCHEMA_ID, field, "STRIP_FIELD",
                f"{field} is assigned by the server on import",
            ))
