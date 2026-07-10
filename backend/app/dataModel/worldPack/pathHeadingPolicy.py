"""Path heading defaults — docs/tz_world_pack_storage.md § WP-16, MERGE-5.

``AppSettings.path_ahead_depth`` counts **macro-tiles** ahead on heading.
Corridor depth in meters: ``depth_tiles * map_cell_size_m``.
Corridor half-width: ``terrain_chunk_columns * corridor_half_width_chunk_multiplier`` meters.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class PathHeadingPolicy(BaseModel):
    """PLAYER_PATH corridor and position-history caps."""

    SCHEMA_ID: ClassVar[str] = "SCH-PATH-HEADING-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    position_history_max: int = 5
    corridor_half_width_chunk_multiplier: float = 1.0

    @classmethod
    def canonical_defaults(cls) -> PathHeadingPolicy:
        return cls()

    def corridor_half_width_m(self, terrain_chunk_columns: int) -> float:
        return float(terrain_chunk_columns) * self.corridor_half_width_chunk_multiplier
