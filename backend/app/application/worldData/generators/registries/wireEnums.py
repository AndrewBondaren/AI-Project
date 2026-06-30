"""ENUM-E wire values — docs/tz_json_validation.md JV-0/JV-2."""

from __future__ import annotations

from enum import StrEnum


class ConnectionNodeType(StrEnum):
    INTERSECTION = "intersection"
    SETTLEMENT_GATE = "settlement_gate"
    PORTAL = "portal"
    BUILDING_ENTRANCE = "building_entrance"
    LOCATION_HUB = "location_hub"
    WAYPOINT = "waypoint"


class GraphLevel(StrEnum):
    WORLD = "world"
    CITY = "city"
    DISTRICT = "district"
    AREA = "area"


class HydrologyConnectionType(StrEnum):
    LAKE_SHORELINE = "lake_shoreline"
    COASTLINE = "coastline"
    RIVER = "river"
    MOUNTAIN_RIVER = "mountain_river"


class BridgeSubtype(StrEnum):
    PEDESTRIAN = "pedestrian"
    TRANSPORT = "transport"
    VIADUCT = "viaduct"


class SidewalkSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class PortalType(StrEnum):
    COORDINATE = "coordinate"
    GRAPH = "graph"
