"""``world.terrain_masks`` POJOs."""

from app.dataModel.terrainMasks.mountain import (
    MountainDeclareEntry,
    MountainForm,
    MountainFormBySides,
    MountainKind,
    MountainRangeSides,
    MountainRangeSpec,
    MountainRangeStyle,
    MountainSaddleSpec,
    MountainSideKind,
    MountainSideSpec,
    MountainSpec,
    PeakForm,
    PlateauForm,
    StarForm,
    mountain_kind_profile,
)
from app.dataModel.terrainMasks.hillPolicy import HillPolicy
from app.dataModel.terrainMasks.hillShape import HillShape
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import (
    MountainsCategoryPolicy,
    RavinesCategoryPolicy,
    RoadsCategoryPolicy,
    WorldTerrainMasks,
)

__all__ = [
    "HillPolicy",
    "HillShape",
    "LandcoverRegionsCategoryPolicy",
    "MountainDeclareEntry",
    "MountainForm",
    "MountainFormBySides",
    "MountainKind",
    "MountainRangeSides",
    "MountainRangeSpec",
    "MountainRangeStyle",
    "MountainSaddleSpec",
    "MountainSideKind",
    "MountainSideSpec",
    "MountainSpec",
    "MountainsCategoryPolicy",
    "PeakForm",
    "PlateauForm",
    "RavinesCategoryPolicy",
    "RoadsCategoryPolicy",
    "StarForm",
    "WorldTerrainMasks",
    "mountain_kind_profile",
]
