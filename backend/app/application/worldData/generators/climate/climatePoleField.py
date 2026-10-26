"""Legacy live-world adapter over the shared frozen-profile sampler."""

from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry

from dataclasses import dataclass

from app.application.jsonValidation import climate_scalars
from app.application.worldData.generators.climate.planning.climatePlanSampler import sample_resolved_profiles
from app.application.worldData.generators.climate.registry import profile_for
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.planning.climatePoints import (
    ClimateKey, ClimatePolePoint, PoleClimateSample as PoleClimateSample,
)
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.spatial.grid.gridBBox import GridBBox as GridBBox
from app.db.models.world import World


@dataclass(frozen=True)
class ClimatePoleField:
    """Compatibility view; frozen sampling uses the same profile kernel."""

    poles: tuple[ClimatePolePoint, ...]
    bbox: GridBBox | None = None

    def is_empty(self) -> bool:
        return not self.poles

    def sample(self, world: World, gx: int, gy: int) -> PoleClimateSample:
        default = RegistryKey[WorldClimateZoneRegistry](climate_scalars(world).default_climate_zone)
        keys = dict.fromkeys((default, *(pole.system_climate_zone for pole in self.poles)))
        profiles = {key: profile_for(world, key) for key in keys}
        return sample_resolved_profiles(self.poles, self.bbox, default, profiles, CLIMATE_POLE_BLEND,
                                         GridX(gx), GridY(gy))
