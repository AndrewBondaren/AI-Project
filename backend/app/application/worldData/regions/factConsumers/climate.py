"""Climate facts from the prepared local field and resolved world profiles."""

from math import fsum

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ClimateFacts


def contribute(context: FactConsumerContext) -> ClimateFacts | None:
    if context.surface is None or context.climate_profiles is None or not context.cells:
        return None
    profiles = []
    for gx, gy in sorted(set(context.cells)):
        anchor = context.surface.local_field.nearest(gx, gy)
        profile = context.climate_profiles.get(anchor.system_climate_zone) if anchor else None
        if profile is None:
            return None  # Incomplete scope is not silently averaged over a smaller region.
        profiles.append(profile)
    return ClimateFacts(
        rainfall_mean=fsum(p.base_rainfall for p in profiles) / len(profiles),
        temperature=fsum(p.base_temperature for p in profiles) / len(profiles),
    )
