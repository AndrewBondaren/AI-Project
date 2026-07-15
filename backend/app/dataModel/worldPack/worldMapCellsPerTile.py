"""WP-10 v2: world_map_cells_per_tile — constant mask side (default 32).

See ``docs/tz_world_pack_storage.md`` § L0 / WP-10 v2.
``light_m = map_cell_size_m // side`` — physical scale drifts with tile size;
``side`` itself does **not** depend on ``map_cell_size_m``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

WORLD_MAP_CELLS_PER_TILE = 32


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
        if override is not None:
            return max(1, int(override))
        return max(1, int(self.cells_per_tile))

    def resolve(self, map_cell_size_m: int, override: int | None = None) -> int:
        """Compat wrapper — ``map_cell_size_m`` ignored (affects ``light_m``, not side)."""
        del map_cell_size_m
        return self.resolve_side(override)


def resolve_world_map_cells_per_tile(
    map_cell_size_m: int,
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    """Return L0 mask side. ``map_cell_size_m`` does not change side (WP-10 v2)."""
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve(map_cell_size_m, override)


def resolve_world_map_side(
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    """Preferred API — side only, no misleading tile_m argument."""
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve_side(override)


def light_m_for(tile_m: int, side: int) -> int:
    """Meters per light cell: ``map_cell_size_m // side`` (WP-10).

    Single SoT for ``LightGridScale.light_m`` and ``ParentLightTile.light_m``.
    """
    return max(1, int(tile_m) // max(1, int(side)))
