"""MergedCellView → MapCell for debug export and scene reads."""

from __future__ import annotations

from app.dataModel.worldPack.mergeMapCells import MergedCellView
from app.db.models.mapCell import MapCell


def merged_view_to_map_cell(world_uid: str, view: MergedCellView) -> MapCell:
    return MapCell(
        world_uid=world_uid,
        x=view.x,
        y=view.y,
        z=view.z,
        system_terrain=view.system_terrain,
        system_material=view.system_material,
        system_building_element=view.system_building_element,
        temperature_base=view.temperature_base,
        rainfall=view.rainfall,
        location_uid=view.location_uid,
        hydrology=view.hydrology,
        is_structural=view.is_structural,
        travel_modifier_override=view.travel_modifier_override,
    )
