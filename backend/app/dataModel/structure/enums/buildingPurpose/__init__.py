"""Building purpose catalog — families, leaves, world packs.

Public import path stays ``app.dataModel.structure.enums.buildingPurpose``.
tz_building_generator.md §2.1.
"""

from .catalog import (
    DEFAULT_BUILDING_PURPOSES,
    DEFAULT_PURPOSE_MATCH,
    FAMILY_OF,
    HOUSE,
    PACK_PURPOSES,
    PURPOSE_DISPLAY,
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeMatch,
    children_of,
    coerce_allowed_list,
    coerce_purpose_list,
    coerce_purpose_match,
    expand_allowed,
    primary_purpose,
    purposes_for_world,
    purposes_match,
    union_plot_purposes,
)
from .family import BuildingPurposeFamily
from .packs import PurposePack, coerce_purpose_packs
from .worldPurposePacks import WorldPurposePacks

__all__ = [
    "AllowedToken",
    "BuildingPurpose",
    "BuildingPurposeFamily",
    "BuildingPurposeMatch",
    "DEFAULT_BUILDING_PURPOSES",
    "DEFAULT_PURPOSE_MATCH",
    "FAMILY_OF",
    "HOUSE",
    "PACK_PURPOSES",
    "PURPOSE_DISPLAY",
    "PurposePack",
    "WorldPurposePacks",
    "children_of",
    "coerce_allowed_list",
    "coerce_purpose_list",
    "coerce_purpose_match",
    "coerce_purpose_packs",
    "expand_allowed",
    "primary_purpose",
    "purposes_for_world",
    "purposes_match",
    "union_plot_purposes",
]
