"""Map L0 hydrology role from coarse hydrology cells."""

from __future__ import annotations

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.hydrologyMaskWire import L0HydrologyRole


def l0_hydro_role_from_cell(cell_hydro: object | None) -> L0HydrologyRole:
    if cell_hydro is None:
        return L0HydrologyRole.NONE
    role: HydrologyCellRole | None = None
    if isinstance(cell_hydro, MapCellHydrology):
        role = cell_hydro.role
    elif isinstance(cell_hydro, dict):
        role = HydrologyCellRole.from_wire(cell_hydro.get("role"))
    else:
        raw = getattr(cell_hydro, "role", None)
        if isinstance(raw, HydrologyCellRole):
            role = raw
        elif raw is not None:
            role = HydrologyCellRole.from_wire(str(getattr(raw, "value", raw)))
    if role is None:
        return L0HydrologyRole.NONE
    match role:
        case HydrologyCellRole.RIVER_BED:
            return L0HydrologyRole.RIVER
        case HydrologyCellRole.SHORE:
            return L0HydrologyRole.SHORE
        case HydrologyCellRole.LAKE | HydrologyCellRole.INLAND_SEA:
            return L0HydrologyRole.LAKE
        case HydrologyCellRole.COASTAL_SEA | HydrologyCellRole.OPEN_OCEAN:
            return L0HydrologyRole.SEA
        case _:
            return L0HydrologyRole.NONE
