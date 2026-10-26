"""Climate facts from the prepared local field and resolved world profiles."""

from math import fsum

from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ClimateFacts
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile


def contribute(context: FactConsumerContext) -> ClimateFacts | None:
    field = _local_field(context)
    if field is None or not context.cells:
        return None
    profiles = []
    for gx, gy in sorted(set(context.cells)):
        anchor = field.nearest(gx, gy)
        profile = _profile_for_anchor(context, anchor) if anchor is not None else None
        if profile is None:
            return None  # Incomplete scope is not silently averaged over a smaller region.
        profiles.append(profile)
    return ClimateFacts(
        rainfall_mean=fsum(p.base_rainfall for p in profiles) / len(profiles),
        temperature=fsum(p.base_temperature for p in profiles) / len(profiles),
    )


def _local_field(context: FactConsumerContext) -> ClimateAnchorField | None:
    if context.climate is not None:
        return context.climate.local_field
    if context.local_field is not None:
        return context.local_field
    return context.surface.local_field if context.surface is not None else None


def _profile_for_anchor(context: FactConsumerContext, anchor: ClimateAnchorPoint) -> ClimateZoneProfile | None:
    if context.climate is not None:
        return context.climate.profile_for_key(anchor.system_climate_zone)
    if context.climate_profiles is None:
        return None
    return context.climate_profiles.get(anchor.system_climate_zone)
