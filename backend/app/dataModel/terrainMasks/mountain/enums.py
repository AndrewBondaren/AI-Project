"""Mountain engine enums + kind profiles — tz_map_light_bake § Mountain (engine)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrain.relief.enums import ReliefSideKind

# Shim → relief domain SoT (tz_terrain_relief R6).
MountainSideKind = ReliefSideKind


class MountainKind(StrEnum):
    ROCKY = "rocky"
    ICE_PEAK = "ice_peak"
    VOLCANO = "volcano"
    PLATEAU = "plateau"
    FORESTED = "forested"


class MountainRangeStyle(StrEnum):
    """Spine sample style — tz_mountain_architecture."""

    BROKEN = "broken"
    SMOOTH = "smooth"
    HYBRID = "hybrid"


class MountainKindProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    rise_fraction_of_z_max: float = constrained_field(
        default=0.35, greater_equals=0.0, lesser_equals=1.0,
    )
    # TODO(U7): per-kind inset calibration — docs/tz_mountain_architecture.md U7
    peak_gap_inset_fraction: float = constrained_field(
        default=0.30, greater_equals=0.0, lesser_equals=1.0,
    )
    saddle_rise_fraction: float = constrained_field(
        default=0.65, greater_equals=0.0, lesser_equals=1.0,
    )


_KIND_PROFILES: dict[MountainKind, MountainKindProfile] = {
    MountainKind.ROCKY: MountainKindProfile(rise_fraction_of_z_max=0.35),
    MountainKind.ICE_PEAK: MountainKindProfile(rise_fraction_of_z_max=0.45),
    MountainKind.VOLCANO: MountainKindProfile(rise_fraction_of_z_max=0.40),
    MountainKind.PLATEAU: MountainKindProfile(rise_fraction_of_z_max=0.25),
    MountainKind.FORESTED: MountainKindProfile(rise_fraction_of_z_max=0.20),
}


def mountain_kind_profile(kind: MountainKind) -> MountainKindProfile:
    return _KIND_PROFILES[kind]


class MountainFormType(StrEnum):
    BY_SIDES = "by_sides"
    STAR = "star"
    PEAK = "peak"
    PLATEAU = "plateau"
