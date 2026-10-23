"""Complete source projection for base climate planning."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.climate.climatePoleBlendDefaults import ClimatePoleBlendDefaults
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.planning.climatePlan import ResolvedClimateProfile, require_profiles
from app.dataModel.climate.planning.climatePoints import ClimateKey
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.spatial.grid.gridBBox import GridBBox


class ManualPoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    location_uid: EntityUid
    position: FineXY
    kind: PoleKind
    zone: ClimateKey | None


class ClimateBaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    seed: StrictInt
    bbox: GridBBox | None
    fine_span: StrictInt = Field(gt=0)
    mode: ClimatePoleMode
    preset: ClimatePolePreset
    peak_min: StrictInt
    peak_max: StrictInt
    default_zone: ClimateKey
    manual_poles: tuple[ManualPoleInput, ...]
    profiles: tuple[ResolvedClimateProfile, ...]
    blend: ClimatePoleBlendDefaults

    @model_validator(mode="after")
    def complete_inputs(self) -> Self:
        if self.peak_min > self.peak_max:
            raise ValueError("peak_min exceeds peak_max")
        required = {self.default_zone, *(pole.zone for pole in self.manual_poles if pole.zone is not None),
                    *(spec.system_climate_zone for spec in self.preset.pole_specs())}
        require_profiles(self.profiles, required)
        return self
