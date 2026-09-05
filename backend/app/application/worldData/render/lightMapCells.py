"""WorldMapCellWire → L0 ASCII glyph. Not FineTerrain columns."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.render.locationPinOverlay import l0_settlement_glyph, pin_at
from app.application.worldData.render.mapSymbols import (
    ROAD_TERRAIN_KEY,
    grade_symbol,
    symbol_for_role_or_terrain,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def wire_symbol(
    cell: WorldMapCellWire,
    *,
    mark_pin: bool = False,
    pins: Sequence[LocationsIndexPin] | None = None,
    location_types: WorldLocationTypeRegistry | None = None,
) -> str:
    """Mask glyph. Settlement occupancy from pin subtype. ``@`` is a separate overlay."""
    _ = mark_pin
    if cell.hydrology_role != WorldMapHydrologyRole.NONE:
        fine = cell.hydrology_role.to_fine_role()
        role_name = fine.value if fine is not None else cell.hydrology_role.name.lower()
        return symbol_for_role_or_terrain(
            hydrology_role=role_name,
            system_terrain=cell.system_terrain,
        )
    if cell.system_terrain == ROAD_TERRAIN_KEY:
        return symbol_for_role_or_terrain(system_terrain=ROAD_TERRAIN_KEY)
    if cell.location_pin is not None:
        return l0_settlement_glyph(
            pin_at(pins, cell.location_pin),
            location_types=location_types,
        )
    return symbol_for_role_or_terrain(system_terrain=cell.system_terrain)


def wire_grade_symbol(cell: WorldMapCellWire) -> str:
    """Relief facing overlay — independent of terrain/hydro mask."""
    return grade_symbol(
        system_grade_uid=cell.system_grade_uid,
        system_facing=cell.system_facing,
    )
