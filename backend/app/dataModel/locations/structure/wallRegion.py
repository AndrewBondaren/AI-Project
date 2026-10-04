"""Typed wall-region provenance — tz_building_generator.md §8.7.1.

Internal runtime contract between the pure wall classifier, the material
selector and the single wall writer. Not a wire model and not persisted —
the same DTO serves the future unified staircase placement, which must not
redefine the exterior shell.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WallProvenance(StrEnum):
    """Which side of the wall bounds the building's used volume (§8.7.1)."""

    EXTERIOR = "exterior"  # faces outdoors / unused volume → building shell
    INTERIOR = "interior"  # faces used volume on the inner side(s)


class WallRegion(BaseModel):
    """Physical wall cells sharing one classification.

    `cells` are XY; the region applies to every z in [z_min, z_max] inclusive.
    `room_keys` is the caller-deterministic list of rooms adjacent to the
    region on the used-volume side — material candidates for the selector.
    One physical cell belongs to exactly one region (classifier contract).
    No staircase_type and no material: provenance only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cells: frozenset[tuple[int, int]] = Field(min_length=1)
    z_min: int
    z_max: int
    provenance: WallProvenance
    room_keys: tuple[str, ...] = ()
