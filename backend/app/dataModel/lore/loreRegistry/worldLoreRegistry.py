"""Root POJO for `worlds.lore_registry`. Wire shape: JSON object (map)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.lore.loreRegistry.loreRegistryEntry import LoreRegistryEntry

_CANONICAL_ENTRIES: dict[str, LoreRegistryEntry] = {
    "terrain_plains": LoreRegistryEntry(
        display_name="Равнина",
        description="Открытая ровная местность.",
    ),
    "terrain_forest": LoreRegistryEntry(
        display_name="Лес",
        description="Густой лесной массив.",
    ),
    "terrain_liquid_body": LoreRegistryEntry(
        display_name="Водоём",
        description="Открытая вода: море, озеро, река.",
    ),
    "terrain_mountain": LoreRegistryEntry(
        display_name="Горы",
        description="Высокий рельеф, крутые склоны.",
    ),
    "terrain_shore": LoreRegistryEntry(
        display_name="Берег",
        description="Прибрежная полоса: shore + shallow deepening (U15).",
    ),
    "geo_lake_moon": LoreRegistryEntry(
        display_name="Озеро Лунное",
        description="Declared lake — name + lake_shoreline ConnectionEdge chain (U20).",
    ),
    "geo_peak_white": LoreRegistryEntry(
        display_name="Гора Белая",
        description="Declared peak — river source context.",
    ),
    "geo_sea_north": LoreRegistryEntry(
        display_name="Северное море",
        description="Declared sea — name + coastline ConnectionEdge chain (U21).",
    ),
    "geo_coast_fjord": LoreRegistryEntry(
        display_name="Фьордовый берег",
        description="Declared coast segment.",
    ),
    "geo_river_silver": LoreRegistryEntry(
        display_name="Серебряная река",
        description="Declared river name; geometry via ConnectionEdge.",
    ),
    "geo_island_mist": LoreRegistryEntry(
        display_name="Остров Туманов",
        description="Declared island.",
    ),
    "geo_plain_golden": LoreRegistryEntry(
        display_name="Золотая равнина",
        description="Declared plain — flat bias test.",
    ),
    "geo_mountain_iron": LoreRegistryEntry(
        display_name="Железные горы",
        description="Declared mountain massif.",
    ),
    "terrain_open_space": LoreRegistryEntry(
        display_name="Открытое пространство",
        description="Aerial / open volume.",
    ),
}


class WorldLoreRegistry(RootModel[dict[str, LoreRegistryEntry]]):
    """Root POJO for `worlds.lore_registry`. Key = lore id (`glossary_ref` / `lore_ref`)."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-LORE"

    root: dict[str, LoreRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldLoreRegistry:
        """fixtures/world_template.json."""
        return cls(dict(_CANONICAL_ENTRIES))

    def entry_for(self, lore_id: str) -> LoreRegistryEntry | None:
        return self.root.get(lore_id)

    def lore_ids(self) -> list[str]:
        return sorted(self.root.keys())
