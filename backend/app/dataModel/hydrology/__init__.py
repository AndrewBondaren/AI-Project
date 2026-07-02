"""
SCH-WORLD-HYDROLOGY — `worlds.hydrology` JSON.

Not `worlds.caves.hydrology` (отдельный POJO позже).
Эталон: fixtures/world_template.json, docs/tz_terrain_hydrology.md.
"""

from app.dataModel.hydrology.bands import BAND_MAX, BAND_MIN, HydrologyBands
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
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
    "HydrologyConnectionType",
    "HydrologyShoreDefaults",
    "RiverTypeClassify",
    "HydrologyCategoryPolicy",
    "HydrologyRiversPolicy",
    "HydrologyLakesPolicy",
    "HydrologyLandformsPolicy",
    "HydrologySeasPolicy",
    "WorldHydrology",
]
