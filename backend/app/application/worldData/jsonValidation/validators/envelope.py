"""SCH-WORLD-BUNDLE-ENVELOPE — docs/tz_json_validation.md JV-1."""

from __future__ import annotations

from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationKind
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-WORLD-BUNDLE-ENVELOPE"


class EnvelopeValidator:
    schema_id = SCHEMA_ID
    sections: frozenset[SectionKey] = frozenset()

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.request.kind != ValidationKind.BUNDLE:
            return
        bundle = ctx.bundle
        if not isinstance(bundle, dict):
            ctx.issues.append(error(
                SCHEMA_ID, "$", "INVALID_BUNDLE", "World bundle must be a JSON object",
            ))
            return
        if "world" not in bundle:
            ctx.issues.append(error(
                SCHEMA_ID, "world", "MISSING_KEY", "Bundle must contain 'world' key",
            ))
            return
        world = bundle.get("world")
        if not isinstance(world, dict):
            ctx.issues.append(error(
                SCHEMA_ID, "world", "INVALID_TYPE", "'world' must be an object",
            ))
            return
        uid = world.get("world_uid")
        if not uid or not isinstance(uid, str):
            ctx.issues.append(error(
                SCHEMA_ID, "world.world_uid", "MISSING_FIELD", "world.world_uid is required",
            ))
