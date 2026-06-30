"""CharacterValidationFacade — docs/tz_json_validation.md JV-6."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.character.jsonValidation.types import CharacterValidationContext
from app.application.character.jsonValidation.validators.characterRow import validate_character_row
from app.application.character.jsonValidation.validators.characterSheet import (
    build_stat_schema_map,
    prepare_world_for_character_index,
    validate_character_sheet,
)
from app.application.character.jsonValidation.validators.characterWorldBind import (
    validate_character_world_bind,
)
from app.application.worldData.jsonValidation.index.seedRegistryIndex import (
    SeedRegistryIndex,
    build_seed_registry_index,
)
from app.application.worldData.jsonValidation.index.worldRegistryIndex import (
    build_world_registry_index,
)
from app.application.worldData.jsonValidation.types import (
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)


class CharacterValidationFacade:

    async def validate(self, request: ValidationRequest) -> ValidationResult:
        if request.kind != ValidationKind.CHARACTER:
            return ValidationResult(ok=True)

        if not isinstance(request.payload, dict):
            from app.application.worldData.jsonValidation.validators._issues import error
            return ValidationResult(
                ok=False,
                issues=[error(
                    "SCH-CHARACTER-ROW", "$", "INVALID_TYPE",
                    "character payload must be an object",
                )],
            )

        ctx = _build_context(request)
        validate_character_row(ctx)
        if not ctx.has_errors:
            validate_character_sheet(ctx)
        if not ctx.has_errors:
            validate_character_world_bind(ctx)

        normalized = deepcopy(request.payload)
        if (
            not ctx.has_errors
            and request.expected_world_schema_version
            and normalized.get("world_schema_version") is None
        ):
            normalized["world_schema_version"] = request.expected_world_schema_version

        return ValidationResult(
            ok=not ctx.has_errors,
            issues=list(ctx.issues),
            normalized=normalized,
        )


def _build_context(request: ValidationRequest) -> CharacterValidationContext:
    ctx = CharacterValidationContext(
        request=request,
        sheet=deepcopy(request.payload) if isinstance(request.payload, dict) else None,
    )
    world = request.world_context
    if isinstance(world, dict):
        prepared = prepare_world_for_character_index(world)
        ctx.index = build_world_registry_index(prepared)
        ctx.stat_schema = build_stat_schema_map(prepared)

    if isinstance(request.seed_snapshot, dict):
        ctx.seed_index = build_seed_registry_index(request.seed_snapshot)
    else:
        ctx.seed_index = SeedRegistryIndex()

    if isinstance(request.races_snapshot, list):
        ctx.race_uids = frozenset(
            row["race_uid"]
            for row in request.races_snapshot
            if isinstance(row, dict) and isinstance(row.get("race_uid"), str)
        )

    if isinstance(request.locations_snapshot, list):
        ctx.location_uids = frozenset(
            row["location_uid"]
            for row in request.locations_snapshot
            if isinstance(row, dict) and isinstance(row.get("location_uid"), str)
        )

    return ctx
