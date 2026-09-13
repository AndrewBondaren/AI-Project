"""Building purpose catalog — families, leaves, world packs.

Public import path stays ``app.dataModel.structure.enums.buildingPurpose``.
tz_building_generator.md §2.1.
"""

from .catalog import (
    DEFAULT_BUILDING_PURPOSES,
    DEFAULT_PURPOSE_MATCH,
    FAMILY_OF,
    HOUSE,
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeMatch,
    children_of,
    coerce_allowed_list,
    coerce_purpose_list,
    coerce_purpose_match,
    expand_allowed,
    leaves_for_family,
    primary_purpose,
    purposes_match,
    union_plot_purposes,
)
from .family import BuildingPurposeFamily
from .packs import PurposePack, coerce_purpose_packs, normalize_pack_id
from .purposePackEntry import PurposePackEntry
from .worldPurposePackRegistry import (
    PurposePackKey,
    WorldPurposePackRegistry,
    purposes_for_world,
)
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
    "PurposePack",
    "PurposePackEntry",
    "PurposePackKey",
    "WorldPurposePackRegistry",
    "WorldPurposePacks",
    "children_of",
    "coerce_allowed_list",
    "coerce_purpose_list",
    "coerce_purpose_match",
    "coerce_purpose_packs",
    "expand_allowed",
    "leaves_for_family",
    "normalize_pack_id",
    "primary_purpose",
    "purposes_for_world",
    "purposes_match",
    "union_plot_purposes",
]
