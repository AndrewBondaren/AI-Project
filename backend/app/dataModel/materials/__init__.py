"""
SCH-WORLD-MATERIAL — `worlds.material_registry` JSON array (N1-W-01).

Эталон: fixtures/world_template.json, docs/tz_materials.md.
"""

from app.dataModel.materials.constructionMaterialDefaults import (
    CONSTRUCTION_MATERIAL_DEFAULTS,
    DEFAULT_DOMINANT_MATERIAL,
    DEFAULT_FLOOR_MATERIAL,
    DEFAULT_ROAD_MATERIAL,
    DEFAULT_WALL_MATERIAL,
    ConstructionMaterialDefaults,
)
from app.dataModel.materials.materialRegistryEntry import (
    HARDNESS_MAX,
    HARDNESS_MIN,
    MaterialRegistryEntry,
)
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry

__all__ = [
    "CONSTRUCTION_MATERIAL_DEFAULTS",
    "DEFAULT_DOMINANT_MATERIAL",
    "DEFAULT_FLOOR_MATERIAL",
    "DEFAULT_ROAD_MATERIAL",
    "DEFAULT_WALL_MATERIAL",
    "ConstructionMaterialDefaults",
    "HARDNESS_MIN",
    "HARDNESS_MAX",
    "MaterialCategory",
    "MaterialRegistryEntry",
    "WorldMaterialRegistry",
]
