"""Independent generation axis and category selector; rivers use their own track."""

from enum import StrEnum

from app.dataModel.cascade.cascadeSpec import ScopeAxis


class WaterGenerationScope(ScopeAxis):
    ROOT = "root"
    WORLD = "world"
    CATEGORY = "category"
    WATER_BODY = "water_body"


class WaterGenerationCategory(StrEnum):
    SEA = "sea"
    OCEAN = "ocean"
    LAKE = "lake"
