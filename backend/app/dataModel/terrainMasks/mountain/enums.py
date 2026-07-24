"""Mountain engine enums + kind profiles — tz_map_light_bake § Mountain (engine)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.constrainedField import constrained_field


class MountainKind(StrEnum):
    ROCKY = "rocky"
    ICE_PEAK = "ice_peak"
    VOLCANO = "volcano"
    PLATEAU = "plateau"
    FORESTED = "forested"


class MountainKindProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    rise_fraction_of_z_max: float = constrained_field(
        default=0.35, greater_equals=0.0, lesser_equals=1.0,
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


class MountainSideKind(StrEnum):
    SHEER = "sheer"
    SLOPE = "slope"


class MountainFormType(StrEnum):
    BY_SIDES = "by_sides"
    STAR = "star"
    PEAK = "peak"
    PLATEAU = "plateau"
