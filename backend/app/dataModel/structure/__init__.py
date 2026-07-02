"""
SCH-STRUCTURE — building/barrier/room master data (outside settlement domain).

Structure templates ≠ settlement layout; settlement references structure via templates.
Эталон: docs/tz_building_generator.md, docs/tz_locations.md § structure generation.
"""

from app.dataModel.structure.barrier import BarrierTemplateEntry, WorldBarrierTemplateRegistry
from app.dataModel.structure.building import (
    BuildingTemplateOutline,
    BuildingTemplateRegistryEntry,
    BuildingTemplateRoomSlot,
    WorldBuildingTemplateRegistry,
)
from app.dataModel.structure.enums import (
    DOOR_BUILDING_ELEMENTS,
    PASSABLE_BUILDING_ELEMENTS,
    STAIR_BUILDING_ELEMENTS,
    STAIR_DIRECTIONAL_ELEMENTS,
    StructureElement,
    WALKABLE_BUILDING_ELEMENTS,
    WALL_BUILDING_ELEMENTS,
    WALL_OPENING_ELEMENTS,
    PassageType,
    RoomSize,
    RoomSizePreset,
    SPIRAL_SIZE_PRESETS,
    STRAIGHT_SIZE_PRESETS,
    USHAPE_SIZE_PRESETS,
    SpiralSize,
    StaircaseSizePreset,
    StaircaseType,
    StaircaseTypeSpec,
    StraightSize,
    UShapeSize,
    all_staircase_size_presets,
    default_shaft_footprint_min,
    default_shaft_size_type,
    no_shaft_types,
    requires_shaft,
    staircase_footprint_min,
)
from app.dataModel.structure.materialPick import MaterialPick
from app.dataModel.structure.room import RoomTypeEntry, WorldRoomTypeRegistry

__all__ = [
    "BarrierTemplateEntry",
    "BuildingTemplateOutline",
    "BuildingTemplateRegistryEntry",
    "BuildingTemplateRoomSlot",
    "DOOR_BUILDING_ELEMENTS",
    "MaterialPick",
    "PASSABLE_BUILDING_ELEMENTS",
    "PassageType",
    "RoomSize",
    "RoomSizePreset",
    "SPIRAL_SIZE_PRESETS",
    "STAIR_BUILDING_ELEMENTS",
    "STAIR_DIRECTIONAL_ELEMENTS",
    "STRAIGHT_SIZE_PRESETS",
    "StructureElement",
    "USHAPE_SIZE_PRESETS",
    "SpiralSize",
    "StaircaseSizePreset",
    "StaircaseType",
    "StaircaseTypeSpec",
    "StraightSize",
    "UShapeSize",
    "all_staircase_size_presets",
    "default_shaft_footprint_min",
    "default_shaft_size_type",
    "no_shaft_types",
    "requires_shaft",
    "staircase_footprint_min",
    "RoomTypeEntry",
    "WorldBarrierTemplateRegistry",
    "WorldBuildingTemplateRegistry",
    "WorldRoomTypeRegistry",
    "WALKABLE_BUILDING_ELEMENTS",
    "WALL_BUILDING_ELEMENTS",
    "WALL_OPENING_ELEMENTS",
]
