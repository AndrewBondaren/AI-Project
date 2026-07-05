"""U25 lake vs inland_sea intent from declare subtype — D HY-3."""

from __future__ import annotations

import logging

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.db.models.namedLocation import NamedLocation

logger = logging.getLogger(__name__)


def resolve_lake_basin_role(
    location_uid: str | None,
    locations_by_uid: dict[str, NamedLocation],
    *,
    world_uid: str,
    connection_type: str,
) -> HydrologyCellRole:
    """
    Subtype intent (A); topology mismatch → warning + carve by edge type (B).
    """
    subtype = None
    if location_uid and location_uid in locations_by_uid:
        loc = locations_by_uid[location_uid]
        subtype = GeographicSubtype.from_wire(loc.system_location_subtype)

    if connection_type == "lake_shoreline":
        if subtype == GeographicSubtype.INLAND_SEA:
            logger.warning(
                "basin_kind | world=%s location=%s inland_sea subtype with lake_shoreline; carve as lake",
                world_uid,
                location_uid,
            )
        return HydrologyCellRole.LAKE

    if subtype == GeographicSubtype.LAKE:
        logger.warning(
            "basin_kind | world=%s location=%s lake subtype with non-lake shoreline; carve as lake",
            world_uid,
            location_uid,
        )
    return HydrologyCellRole.LAKE
