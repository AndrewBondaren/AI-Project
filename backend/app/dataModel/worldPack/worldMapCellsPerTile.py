"""WP-10 v2: world_map_cells_per_tile — constant mask side (default 32).

See ``docs/tz_world_pack_storage.md`` § L0 / WP-10 v2.
``light_m = map_cell_size_m // side`` — physical scale drifts with tile size.
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

    def resolve(self, map_cell_size_m: int, override: int | None = None) -> int:
        """Return mask side. Default always 32; optional master override (sanity ≥ 1)."""
        del map_cell_size_m  # scale is light_m = tile_m // side, not side itself
        if override is not None:
            return max(1, int(override))
        return max(1, int(self.cells_per_tile))


def resolve_world_map_cells_per_tile(
    map_cell_size_m: int,
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve(map_cell_size_m, override)
