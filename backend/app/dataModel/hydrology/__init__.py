"""
SCH-WORLD-HYDROLOGY — `worlds.hydrology` JSON.
SCH-MAP-CELL-HYDROLOGY — `map_cells.hydrology` JSON.

Not `worlds.caves.hydrology` (отдельный POJO позже).
Эталон: fixtures/world_template.json, docs/tz_terrain_hydrology.md.
"""

from app.dataModel.hydrology.bands import BAND_MAX, BAND_MIN, HydrologyBands
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.riverSystemTopology import RiverSystemTopology
from app.dataModel.hydrology.mapCellHydrology import (
    MapCellHydrology,
    cell_hydrology_liquid_candidate,
    dump_cell_hydrology,
    parse_cell_hydrology,
)
from app.dataModel.hydrology.category import HydrologyCategoryPolicy
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.landforms import HydrologyLandformsPolicy
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy, RiverTypeClassify
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.hydrology.worldHydrology import WorldHydrology

__all__ = [
    "BAND_MIN",
    "BAND_MAX",
    "HydrologyBands",
    "DeclaredCoastline",
    "DeclaredLake",
    "DeclaredRiver",
    "RiverSystemTopology",
    "HydrologyCellRole",
    "HydrologyConnectionType",
    "MapCellHydrology",
    "HydrologyShoreDefaults",
    "RiverTypeClassify",
    "HydrologyCategoryPolicy",
    "HydrologyRiversPolicy",
    "HydrologyLakesPolicy",
    "HydrologyLandformsPolicy",
    "HydrologySeasPolicy",
    "WorldHydrology",
    "cell_hydrology_liquid_candidate",
    "dump_cell_hydrology",
    "parse_cell_hydrology",
]
