"""WP-10 v2: world_map_cells_per_tile — constant mask side (default 32).

See ``docs/tz_world_pack_storage.md`` § L0 / WP-10 v2.
``light_span = fine_cells_per_map_cell // side`` — physical scale drifts with tile size;
``side`` itself does **not** depend on ``fine_cells_per_map_cell``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.spatial.grid.lightGridScale import light_span_for

__all__ = [
    "WORLD_MAP_CELLS_PER_TILE",
    "WorldMapCellsPerTilePolicy",
    "coerce_world_map_override",
    "light_span_for",
    "resolve_world_map_cells_per_tile",
    "resolve_world_map_side",
]

WORLD_MAP_CELLS_PER_TILE = 32


def coerce_world_map_override(value: Any) -> int | None:
    """Existing override interpretation, shared by world wire and runtime policy."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, OverflowError) as exc:
        raise ValueError("world map override must be convertible to int") from exc


class WorldMapCellsPerTilePolicy(BaseModel):
    """Builtin constant for light-grid resolution — single source of truth."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-MAP-CELLS-PER-TILE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    cells_per_tile: int = WORLD_MAP_CELLS_PER_TILE

    @classmethod
    def canonical_defaults(cls) -> WorldMapCellsPerTilePolicy:
        return cls()

    def resolve_side(self, override: int | None = None) -> int:
        """Return mask side. Default always 32; optional master override (sanity ≥ 1)."""
        override = coerce_world_map_override(override)
        if override is not None:
            return max(1, override)
        return max(1, int(self.cells_per_tile))

    def resolve(self, fine_cells_per_map_cell: int, override: int | None = None) -> int:
        """Compat wrapper — ``fine_cells_per_map_cell`` ignored (affects ``light_span``, not side)."""
        del fine_cells_per_map_cell
        return self.resolve_side(override)


def resolve_world_map_cells_per_tile(
    fine_cells_per_map_cell: int,
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    """Return L0 mask side. ``fine_cells_per_map_cell`` does not change side (WP-10 v2)."""
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve(fine_cells_per_map_cell, override)


def resolve_world_map_side(
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    """Preferred API — side only, no misleading tile_macro argument."""
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve_side(override)

# ``light_span_for`` is re-exported from dataModel/spatial/grid/lightGridScale
# (canonical owner since PC-11.6a); alias resolves in PC-11.6b.
