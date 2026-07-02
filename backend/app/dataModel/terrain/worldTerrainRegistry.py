"""Root POJO for `worlds.terrain_registry` JSON array."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry

# Outdoor + hydrology-facing set — fixtures/world_template.json
_CANONICAL_ENTRIES: tuple[TerrainRegistryEntry, ...] = (
    TerrainRegistryEntry(
        system_terrain="plains",
        glossary_ref="terrain_plains",
        terrain_category="solid",
        travel_modifier=1.5,
        default_material="earth",
    ),
    TerrainRegistryEntry(
        system_terrain="forest",
        glossary_ref="terrain_forest",
        terrain_category="solid",
        travel_modifier=2.5,
        danger_level="medium",
        default_material="wood",
    ),
    TerrainRegistryEntry(
        system_terrain="mountain",
        glossary_ref="terrain_mountain",
        terrain_category="solid",
        travel_modifier=3.0,
        danger_level="medium",
        default_material="stone",
    ),
    TerrainRegistryEntry(
        system_terrain="shore",
        glossary_ref="terrain_shore",
        terrain_category="solid",
        travel_modifier=1.8,
        danger_level="low",
        default_material="sand",
    ),
    TerrainRegistryEntry(
        system_terrain="liquid_body",
        glossary_ref="terrain_liquid_body",
        terrain_category="liquid",
        danger_level="high",
        default_material="water",
    ),
    TerrainRegistryEntry(
        system_terrain="open_space",
        glossary_ref="terrain_open_space",
        terrain_category="aerial",
    ),
)

# Interior / structure types — tz_locations.md full engine set (beyond world_template outdoor slice).
_ENGINE_INTERIOR_ENTRIES: tuple[TerrainRegistryEntry, ...] = (
    TerrainRegistryEntry(
        system_terrain="crevice",
        glossary_ref="terrain_crevice",
        terrain_category="crevice",
        danger_level="high",
        default_material="stone",
        gap_width=2,
    ),
    TerrainRegistryEntry(
        system_terrain="floor",
        glossary_ref="terrain_floor",
        terrain_category="solid",
        travel_modifier=1.0,
    ),
    TerrainRegistryEntry(
        system_terrain="roof",
        glossary_ref="terrain_roof",
        terrain_category="solid",
        travel_modifier=1.0,
    ),
    TerrainRegistryEntry(
        system_terrain="wall",
        glossary_ref="terrain_wall",
        terrain_category="barrier",
    ),
    TerrainRegistryEntry(
        system_terrain="door",
        glossary_ref="terrain_door",
        terrain_category="barrier",
        has_state=True,
        default_state="closed",
    ),
    TerrainRegistryEntry(
        system_terrain="gate",
        glossary_ref="terrain_gate",
        terrain_category="barrier",
        has_state=True,
        default_state="closed",
    ),
    TerrainRegistryEntry(
        system_terrain="window",
        glossary_ref="terrain_window",
        terrain_category="barrier",
        has_state=True,
        default_state="closed",
    ),
    TerrainRegistryEntry(
        system_terrain="rubble",
        glossary_ref="terrain_rubble",
        terrain_category="solid",
        travel_modifier=2.0,
        danger_level="low",
    ),
)


class WorldTerrainRegistry(RootModel[list[TerrainRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TERRAIN"
    """Root POJO for `worlds.terrain_registry`. Wire shape: JSON array."""

    root: list[TerrainRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldTerrainRegistry:
        """Fixture outdoor set — fixtures/world_template.json."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldTerrainRegistry:
        """Outdoor + interior types — tz_locations.md § terrain_registry."""
        return cls(list(_CANONICAL_ENTRIES + _ENGINE_INTERIOR_ENTRIES))

    def entry_for(self, system_terrain: str) -> TerrainRegistryEntry | None:
        for entry in self.root:
            if entry.system_terrain == system_terrain:
                return entry
        return None
