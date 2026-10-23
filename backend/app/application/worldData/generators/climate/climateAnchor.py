from app.dataModel.climate.planning.climatePoints import (
    AnchorSource as AnchorSource, ClimateAnchorPoint as ClimateAnchorPoint,
)
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateFeaturePolicy


CLIMATE_ANCHOR_TYPE = "climate_anchor"
ADMIN_ZONE_TYPES = frozenset({"region", "kingdom", "empire", "duchy"})
MANUAL_EXCLUSION_GRID = ClimateFeaturePolicy.manual_exclusion_grid
