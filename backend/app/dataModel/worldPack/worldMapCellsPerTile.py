"""WP-10: resolve world_map_cells_per_tile from map_cell_size_m.

See ``docs/tz_world_pack_storage.md`` § L0.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

WORLD_MAP_CELL_M_REF = 3000
WORLD_MAP_CELLS_REF = 32
WORLD_MAP_CELLS_MIN = 8
WORLD_MAP_CELLS_MAX = 48


class WorldMapCellsPerTilePolicy(BaseModel):
    """Builtin constants for light-grid resolution — single source of truth."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-MAP-CELLS-PER-TILE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    cell_m_ref: int = WORLD_MAP_CELL_M_REF
    cells_ref: int = WORLD_MAP_CELLS_REF
    cells_min: int = WORLD_MAP_CELLS_MIN
    cells_max: int = WORLD_MAP_CELLS_MAX

    @classmethod
    def canonical_defaults(cls) -> WorldMapCellsPerTilePolicy:
        return cls()

    def resolve(self, map_cell_size_m: int, override: int | None = None) -> int:
        if override is not None:
            return max(self.cells_min, min(self.cells_max, int(override)))
        if map_cell_size_m <= 0:
            return self.cells_ref
        raw = round(self.cells_ref * self.cell_m_ref / map_cell_size_m)
        return max(self.cells_min, min(self.cells_max, int(raw)))


def resolve_world_map_cells_per_tile(
    map_cell_size_m: int,
    override: int | None = None,
    *,
    policy: WorldMapCellsPerTilePolicy | None = None,
) -> int:
    pol = policy or WorldMapCellsPerTilePolicy.canonical_defaults()
    return pol.resolve(map_cell_size_m, override)
