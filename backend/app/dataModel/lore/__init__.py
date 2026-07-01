"""
SCH-WORLD-LORE — `worlds.lore_registry` (N1-W-21).

Эталон: fixtures/world_template.json; inbound refs via `glossary_ref` / `lore_ref`.
"""

from app.dataModel.lore.loreRegistry import LoreRegistryEntry, WorldLoreRegistry

__all__ = [
    "LoreRegistryEntry",
    "WorldLoreRegistry",
]
