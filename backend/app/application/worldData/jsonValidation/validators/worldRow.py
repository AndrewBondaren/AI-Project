"""SCH-WORLD-ROW scalar rules — docs/tz_json_validation.md JV-1."""

from __future__ import annotations

from typing import Any

from app.db.models.world import World

from app.application.worldData.jsonValidation.types import SectionKey, ValidationIssue, ValidationContext
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-WORLD-ROW"


def collect_world_row_issues_from_world(world: World) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    v = world.map_cell_size_m
    if not isinstance(v, int) or isinstance(v, bool):
        issues.append(error(
            SCHEMA_ID, "world.map_cell_size_m", "INVALID_TYPE",
            "map_cell_size_m must be an integer",
        ))
    else:
        if v < 1000:
            issues.append(error(
                SCHEMA_ID, "world.map_cell_size_m", "OUT_OF_RANGE",
                "map_cell_size_m must be at least 1000",
            ))
        elif v % 1000 != 0:
            issues.append(error(
                SCHEMA_ID, "world.map_cell_size_m", "OUT_OF_RANGE",
                "map_cell_size_m must be a multiple of 1000",
            ))

    if world.grid_bbox_padding < 0:
        issues.append(error(
            SCHEMA_ID, "world.grid_bbox_padding", "OUT_OF_RANGE",
            "grid_bbox_padding must be >= 0",
        ))

    chunk = world.terrain_chunk_columns
    if not isinstance(chunk, int) or isinstance(chunk, bool) or chunk < 1:
        issues.append(error(
            SCHEMA_ID, "world.terrain_chunk_columns", "OUT_OF_RANGE",
            "terrain_chunk_columns must be an integer >= 1",
        ))

    depth = world.map_subsurface_depth
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 10:
        issues.append(error(
            SCHEMA_ID, "world.map_subsurface_depth", "OUT_OF_RANGE",
            "map_subsurface_depth must be an integer >= 10",
        ))

    return issues


def collect_world_row_issues(world_data: dict[str, Any]) -> list[ValidationIssue]:
    try:
        world = World(**world_data)
    except TypeError as exc:
        return [error(SCHEMA_ID, "world", "STRUCT", str(exc))]
    except Exception as exc:
        return [error(SCHEMA_ID, "world", "STRUCT", str(exc))]
    return collect_world_row_issues_from_world(world)


class WorldRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.WORLD})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
        if not isinstance(bundle, dict):
            return
        world = bundle.get("world")
        if not isinstance(world, dict):
            return
        ctx.issues.extend(collect_world_row_issues(world))
