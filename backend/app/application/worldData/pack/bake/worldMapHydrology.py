"""World map hydrology role from coarse hydrology cells."""

from __future__ import annotations

import logging

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

logger = logging.getLogger(__name__)


def world_map_hydro_role_from_cell(cell_hydro: object | None) -> WorldMapHydrologyRole:
    if cell_hydro is None:
        return WorldMapHydrologyRole.NONE
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
        else:
            logger.debug(
                "world_map hydro: unsupported cell type=%s → NONE",
                type(cell_hydro).__name__,
            )
            return WorldMapHydrologyRole.NONE
    if role is None:
        logger.debug(
            "world_map hydro: could not parse role from %s → NONE",
            type(cell_hydro).__name__,
        )
        return WorldMapHydrologyRole.NONE
    match role:
        case HydrologyCellRole.RIVER_BED:
            return WorldMapHydrologyRole.RIVER
        case HydrologyCellRole.SHORE:
            return WorldMapHydrologyRole.SHORE
        case HydrologyCellRole.LAKE | HydrologyCellRole.INLAND_SEA:
            return WorldMapHydrologyRole.LAKE
        case HydrologyCellRole.COASTAL_SEA | HydrologyCellRole.OPEN_OCEAN:
            return WorldMapHydrologyRole.SEA
        case _:
            logger.debug(
                "world_map hydro: fine role=%s has no compact wire mapping → NONE",
                role.value,
            )
            return WorldMapHydrologyRole.NONE
