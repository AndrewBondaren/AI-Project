"""Identity scopes: common connectivity and physical level inheritance differ."""

from enum import StrEnum


class WaterSystemKind(StrEnum):
    PHYSICAL_MERGE = "physical_merge"
    CONNECTED = "connected"
