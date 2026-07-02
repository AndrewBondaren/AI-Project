"""Wire `graph_level` — connection graph hierarchy, tz_structure_connections.md."""

from __future__ import annotations

from enum import StrEnum


class GraphLevel(StrEnum):
    WORLD = "world"
    CITY = "city"
    DISTRICT = "district"
    AREA = "area"
