"""Physical basin profile, independent of cell roles and location identity."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.constrainedField import constrained_field


class BasinKind(StrEnum):
    SEA = "sea"
    OCEAN = "ocean"
    INLAND_SEA = "inland_sea"
    LAKE = "lake"


class BasinKindProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    # None = bowl profile (continuous lerp waterline → floor); value = shelf depth as a fraction of total depth.
    shelf_depth_fraction: float | None = constrained_field(default=None, greater_equals=0.0, lesser_equals=1.0)


_KIND_PROFILES: dict[BasinKind, BasinKindProfile] = {
    BasinKind.OCEAN: BasinKindProfile(shelf_depth_fraction=0.15),
    BasinKind.SEA: BasinKindProfile(shelf_depth_fraction=0.30),
    BasinKind.INLAND_SEA: BasinKindProfile(),
    BasinKind.LAKE: BasinKindProfile(),
}


def basin_kind_profile(kind: BasinKind) -> BasinKindProfile:
    return _KIND_PROFILES[kind]
