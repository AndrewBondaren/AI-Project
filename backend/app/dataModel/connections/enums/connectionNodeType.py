"""Wire `node_type` — connection graph node kinds."""

from __future__ import annotations

from enum import StrEnum


class ConnectionNodeType(StrEnum):
    INTERSECTION = "intersection"
    SETTLEMENT_GATE = "settlement_gate"
    PORTAL = "portal"
    BUILDING_ENTRANCE = "building_entrance"
    LOCATION_HUB = "location_hub"
    WAYPOINT = "waypoint"
