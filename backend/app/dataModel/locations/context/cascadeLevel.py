"""Canonical scope order — tz_cascade_context §2.

Pure ordering axis: the enum knows the hierarchy of scopes and nothing
about which models feed which level. Level ↔ source binding lives on
the source fields themselves (``CascadeChannel`` metadata), not here —
different parameters may have different source sets on the same level.
"""

from enum import StrEnum


class CascadeLevel(StrEnum):
    WORLD = "world"
    SETTLEMENT = "settlement"
    DISTRICT = "district"
    AREA = "area"
    BUILDING = "building"
    ROOM = "room"

    @property
    def rank(self) -> int:
        """Declaration order is the hierarchy; no second ordering table."""
        return tuple(type(self)).index(self)
