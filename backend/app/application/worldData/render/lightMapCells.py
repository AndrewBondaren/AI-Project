"""WorldMapCellWire → L0 ASCII glyph. Not FineTerrain columns."""

from __future__ import annotations

from app.application.worldData.render.mapSymbols import (
    LOCATION_PIN_SYMBOL,
    grade_symbol,
    symbol_for_role_or_terrain,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def wire_symbol(cell: WorldMapCellWire, *, mark_pin: bool = False) -> str:
    if mark_pin and cell.location_pin is not None:
        return LOCATION_PIN_SYMBOL
    role_name: str | None = None
    if cell.hydrology_role != WorldMapHydrologyRole.NONE:
        fine = cell.hydrology_role.to_fine_role()
        role_name = fine.value if fine is not None else cell.hydrology_role.name.lower()
    return symbol_for_role_or_terrain(
        hydrology_role=role_name,
        system_terrain=cell.system_terrain,
    )


def wire_grade_symbol(cell: WorldMapCellWire) -> str:
    """Relief facing overlay — independent of terrain/hydro mask."""
    return grade_symbol(
        system_grade_uid=cell.system_grade_uid,
        system_facing=cell.system_facing,
    )
