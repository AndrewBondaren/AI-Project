"""
SCH-WORLD-MATERIAL — `worlds.material_registry` JSON array (N1-W-01).

Эталон: fixtures/world_template.json, docs/tz_materials.md.
"""

from app.dataModel.materials.materialRegistryEntry import (
    HARDNESS_MAX,
    HARDNESS_MIN,
    MaterialRegistryEntry,
)
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry

__all__ = [
    "HARDNESS_MIN",
    "HARDNESS_MAX",
    "MaterialRegistryEntry",
    "WorldMaterialRegistry",
]
