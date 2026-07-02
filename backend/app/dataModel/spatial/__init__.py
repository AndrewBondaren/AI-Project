"""Spatial ENUM-E — facing, bbox edges (shared by structure, settlement, roads)."""

from app.dataModel.spatial.facing import (
    CARDINAL_FACINGS,
    EW_FACINGS,
    INTERCARDINAL_FACINGS,
    NS_FACINGS,
    OPPOSITE,
    Facing,
    is_corner,
    is_latitudinal_edge,
    is_meridional_edge,
    opposite,
    parse_facing,
    snap_bbox_edge_to_grid,
)

__all__ = [
    "CARDINAL_FACINGS",
    "EW_FACINGS",
    "Facing",
    "INTERCARDINAL_FACINGS",
    "NS_FACINGS",
    "OPPOSITE",
    "is_corner",
    "is_latitudinal_edge",
    "is_meridional_edge",
    "opposite",
    "parse_facing",
    "snap_bbox_edge_to_grid",
]
