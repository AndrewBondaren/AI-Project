"""Frozen climate field data, with complete resolved profile values."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.climate.climatePoleBlendDefaults import ClimatePoleBlendDefaults
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.planning.climatePoints import ClimateAnchorPoint, ClimateKey, ClimatePolePoint
from app.dataModel.spatial.grid.gridBBox import GridBBox


class ResolvedClimateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: ClimateKey
    values: ClimateZoneProfileData


def require_profiles(profiles: tuple[ResolvedClimateProfile, ...], required: set[str]) -> None:
    keys = {profile.key for profile in profiles}
    if len(keys) != len(profiles):
        raise ValueError("duplicate climate profile key")
    if not required <= keys:
        raise ValueError(f"missing climate profiles: {sorted(required - keys)}")


class ClimateBasePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    poles: tuple[ClimatePolePoint, ...]
    bbox: GridBBox | None
    default_zone: ClimateKey
    profiles: tuple[ResolvedClimateProfile, ...]
    blend: ClimatePoleBlendDefaults

    @model_validator(mode="after")
    def complete_profiles(self) -> Self:
        require_profiles(self.profiles, {self.default_zone, *(pole.system_climate_zone for pole in self.poles)})
        return self


class ClimateLocalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    anchors: tuple[ClimateAnchorPoint, ...]


type ClimatePlan = ClimateBasePlan | ClimateLocalPlan
