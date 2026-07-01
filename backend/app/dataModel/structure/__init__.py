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
from app.dataModel.structure.materialPick import MaterialPick
from app.dataModel.structure.room import RoomTypeEntry, WorldRoomTypeRegistry

__all__ = [
    "BarrierTemplateEntry",
    "BuildingTemplateOutline",
    "BuildingTemplateRegistryEntry",
    "BuildingTemplateRoomSlot",
    "MaterialPick",
    "RoomTypeEntry",
    "WorldBarrierTemplateRegistry",
    "WorldBuildingTemplateRegistry",
    "WorldRoomTypeRegistry",
]
