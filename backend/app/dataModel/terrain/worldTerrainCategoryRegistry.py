"""Root POJO for `worlds.terrain_category_registry` JSON array."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.terrain.terrainCategoryEntry import TerrainCategoryEntry

_CANONICAL_ENTRIES: tuple[TerrainCategoryEntry, ...] = (
    TerrainCategoryEntry(system_category="solid", passable=True),
    TerrainCategoryEntry(system_category="liquid", passable=False),
    TerrainCategoryEntry(system_category="aerial", passable=False),
    TerrainCategoryEntry(system_category="crevice", passable=False, jumpable=True),
    TerrainCategoryEntry(system_category="barrier", passable=False, climbable=True, breakable=True),
)


class WorldTerrainCategoryRegistry(RootModel[list[TerrainCategoryEntry]]):
    """Root POJO for `worlds.terrain_category_registry`. Wire shape: JSON array."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TERRAIN-CATEGORY"

    root: list[TerrainCategoryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldTerrainCategoryRegistry:
        """Engine defaults when registry absent — tz_locations.md § terrain_category_registry."""
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_category: str) -> TerrainCategoryEntry | None:
        for entry in self.root:
            if entry.system_category == system_category:
                return entry
        return None
