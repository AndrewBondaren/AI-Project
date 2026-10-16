"""Scoped world mutation and shared invalidation policy; caller owns I/O."""

from collections.abc import Mapping
from typing import Any

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.db.models.world import World


COLUMN_INVALIDATES: dict[str, frozenset[str]] = {
    "fine_cells_per_map_cell": frozenset({"map_cells"}),
}


def invalidated_world_tables(before: Mapping[str, Any],
                             after: Mapping[str, Any]) -> frozenset[str]:
    """Union consequences for actual changes in the supplied normalized wire.

    Only keys in after are being written. The master path may pass the whole
    normalized document; scoped writes pass just their authored columns.
    """
    return frozenset(
        table for key, value in after.items()
        if key in COLUMN_INVALIDATES and (key not in before or before[key] != value)
        for table in COLUMN_INVALIDATES[key]
    )


def apply_world_column(world: World, key: str, raw: Any,
                       ctx: ResolveContext) -> frozenset[str]:
    """Validate before mutation; no repository, transaction or cleanup here."""
    resolved = resolve_world_column(key, raw, ctx, existing=world)
    before = {column: getattr(world, column) for column in resolved}
    invalidated = invalidated_world_tables(before, resolved)
    for column, value in resolved.items():
        setattr(world, column, value)
    return invalidated


def apply_prepared_world_columns(world: World, prepared: Mapping[str, Any]) -> frozenset[str]:
    """Apply values already resolved by the caller's pure preparation stage."""
    before = {column: getattr(world, column) for column in prepared}
    invalidated = invalidated_world_tables(before, prepared)
    for column, value in prepared.items():
        setattr(world, column, value)
    return invalidated
