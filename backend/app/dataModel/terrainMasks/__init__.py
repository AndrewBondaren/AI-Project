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
from app.dataModel.terrainMasks.worldTerrainMasks import (
    ForestsCategoryPolicy,
    MountainsCategoryPolicy,
    PlainsCategoryPolicy,
    RavinesCategoryPolicy,
    RoadsCategoryPolicy,
    WorldTerrainMasks,
)

__all__ = [
    "ForestsCategoryPolicy",
    "HillPolicy",
    "HillShape",
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
    "PlainsCategoryPolicy",
    "PlateauForm",
    "RavinesCategoryPolicy",
    "RoadsCategoryPolicy",
    "StarForm",
    "WorldTerrainMasks",
    "mountain_kind_profile",
]
