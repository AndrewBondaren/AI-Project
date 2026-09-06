"""Wire ``resource_kind`` — ENUM-E for extractable resources. tz_locations.md § resources."""

from __future__ import annotations

from enum import StrEnum


class ResourceKind(StrEnum):
    """How this resource is extracted. N+1 instances are ``system_resource`` rows."""

    ORE = "ore"
    STONE = "stone"
    TIMBER = "timber"
    LIQUID = "liquid"
