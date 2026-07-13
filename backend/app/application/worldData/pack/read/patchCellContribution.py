"""MapCell patch row ↔ CellContribution — application mapping (WP-FIX-DEBT-2)."""

from __future__ import annotations

from app.dataModel.worldPack.mapCellPatchLayerKind import MapCellPatchLayerKind
from app.dataModel.worldPack.mergeMapCells import CellContribution
from app.db.models.mapCell import MapCell

_SAVE_PASS_MAP: dict[str, MapCellPatchLayerKind] = {
    "terrain": MapCellPatchLayerKind.TERRAIN_DELTA,
    "climate": MapCellPatchLayerKind.CLIMATE_DELTA,
    "ore": MapCellPatchLayerKind.ORE,
    "cave": MapCellPatchLayerKind.CAVE,
}


def patch_kind_for_save_pass(layer: str) -> MapCellPatchLayerKind:
    return _SAVE_PASS_MAP.get(layer, MapCellPatchLayerKind.STRUCTURE)


def map_cell_to_patch_contribution(cell: MapCell) -> CellContribution:
    """Field-wise read: all populated patch columns, regardless of ``layer_kind``.

    Write paths merge fields onto one row per (x,y,z); read must not filter by
    the last ``layer_kind`` stamp (WP-FIX-DEBT-1).
    """
    return CellContribution(
        x=cell.x,
        y=cell.y,
        z=cell.z,
        system_terrain=cell.system_terrain,
        system_material=cell.system_material,
        system_building_element=cell.system_building_element,
        temperature_base=cell.temperature_base,
        rainfall=cell.rainfall,
        location_uid=cell.location_uid,
        hydrology=cell.hydrology,
        is_structural=cell.is_structural if cell.is_structural else None,
        travel_modifier_override=cell.travel_modifier_override,
    )
