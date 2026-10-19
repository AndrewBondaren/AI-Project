"""water_body_uid stamp rules — docs/tz_terrain_hydrology.md § Persist map_cells.hydrology (C2)."""

from enum import StrEnum


class AutoWaterBodyRole(StrEnum):
    LAKE = "lake"
    SEA = "sea"
    RIVER = "river"


def auto_water_body_uid(role: AutoWaterBodyRole, anchor: tuple[int, int]) -> str:
    """Positional, non-durable identity for policy-enabled autoresolve carves."""
    return f"auto-{role.value}-{anchor[0]}x{anchor[1]}"


def water_body_uid_for(location_uid: str | None, role: AutoWaterBodyRole, anchor: tuple[int, int]) -> str:
    """Declared identity wins; otherwise the positional auto uid."""
    return location_uid or auto_water_body_uid(role, anchor)
