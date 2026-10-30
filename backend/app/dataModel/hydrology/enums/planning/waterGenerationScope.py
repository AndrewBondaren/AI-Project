"""Independent generation axis and category selector; rivers use their own track."""

from enum import StrEnum

from app.dataModel.cascade.cascadeSpec import ScopeAxis
from app.dataModel.hydrology.enums.basinKind import BasinKind


class WaterGenerationScope(ScopeAxis):
    ROOT = "root"
    WORLD = "world"
    CATEGORY = "category"
    WATER_BODY = "water_body"


class WaterGenerationCategory(StrEnum):
    SEA = "sea"
    OCEAN = "ocean"
    LAKE = "lake"

    @classmethod
    def for_basin_kind(cls, kind: BasinKind) -> "WaterGenerationCategory":
        if not isinstance(kind, BasinKind):
            raise ValueError("water generation category requires BasinKind")
        return {BasinKind.SEA: cls.SEA, BasinKind.INLAND_SEA: cls.SEA,
                BasinKind.OCEAN: cls.OCEAN, BasinKind.LAKE: cls.LAKE}[kind]
