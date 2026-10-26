"""Climate geometry and profile access for one materialization request."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import Lock
from types import MappingProxyType
from typing import Self

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.climatePoints import ClimateKey, PoleClimateSample
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY


@dataclass(frozen=True, slots=True)
class ClimateWorkingFields:
    _base: ClimateBasePlan
    pole_field: ClimatePoleField
    local_field: ClimateAnchorField
    _profiles: Mapping[ClimateKey, ClimateZoneProfile] = field(repr=False)
    _resolver: Callable[[ClimateKey], ClimateZoneProfile] = field(repr=False, compare=False)
    _memo: dict[ClimateKey, ClimateZoneProfile] = field(repr=False, compare=False)
    _lock: Lock = field(repr=False, compare=False)

    @classmethod
    def from_plans(cls, base: ClimateBasePlan, local: ClimateLocalPlan,
                   profile_resolver: Callable[[ClimateKey], ClimateZoneProfile]) -> Self:
        profiles = {entry.key: ClimateZoneProfile.from_data(entry.key, entry.values)
                    for entry in base.profiles}
        return cls(base, ClimatePoleField(base.poles, base.bbox), ClimateAnchorField(local.anchors),
                   MappingProxyType(profiles), profile_resolver, {}, Lock())

    def profile_for_key(self, zone: ClimateKey) -> ClimateZoneProfile:
        with self._lock:
            frozen = self._profiles.get(zone)
            if frozen is not None:
                return frozen
            cached = self._memo.get(zone)
            if cached is not None:
                return cached
            resolved = self._resolver(zone)
            self._memo[zone] = resolved
            return resolved

    def sample_pole(self, gx: GridX, gy: GridY) -> PoleClimateSample:
        return ClimatePlanSampler.sample_prepared(self._base, self._profiles, gx, gy)
