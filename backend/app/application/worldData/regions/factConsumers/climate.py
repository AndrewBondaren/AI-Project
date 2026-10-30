"""Climate facts from the prepared local field and resolved world profiles."""

from math import fsum
from collections.abc import Mapping

from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.climatePoints import ClimateKey
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ClimateFacts


def contribute(context: FactConsumerContext) -> ClimateFacts | None:
    if context.climate is None or not context.cells:
        return None
    field = context.climate.local_field
    profiles = []
    for gx, gy in sorted(set(context.cells)):
        anchor = field.nearest(gx, gy)
        profile = context.climate.profile_for_key(anchor.system_climate_zone) if anchor is not None else None
        if profile is None:
            return None  # Incomplete scope is not silently averaged over a smaller region.
        profiles.append(profile)
    return _aggregate(profiles)


def _aggregate(profiles: list[ClimateZoneProfile]) -> ClimateFacts | None:
    if not profiles:
        return None
    return ClimateFacts(
        rainfall_mean=fsum(p.base_rainfall for p in profiles) / len(profiles),
        temperature=fsum(p.base_temperature for p in profiles) / len(profiles),
    )


def contribute_base(base: ClimateBasePlan, profiles: Mapping[ClimateKey, ClimateZoneProfile],
                    cells: tuple[tuple[int, int], ...]) -> ClimateFacts | None:
    """Pre-water facts from pole profiles; no fabricated local climate field."""
    return _aggregate([profiles[ClimatePlanSampler.sample_prepared(base, profiles, GridX(gx), GridY(gy)).system_climate_zone]
                       for gx, gy in sorted(set(cells))])
