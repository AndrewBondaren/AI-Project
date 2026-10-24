"""Relief-only elevation observations (before hydrology carve)."""

from math import fsum

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ReliefFacts


def contribute(context: FactConsumerContext) -> ReliefFacts | None:
    surface_z = context.relief_z
    if surface_z is None and context.surface is not None:
        surface_z = context.surface.coarse_relief_z
    if surface_z is None or not context.cells:
        return None
    heights: list[int] = []
    for cell in sorted(set(context.cells)):
        height = surface_z.get(cell)
        if height is None:
            return None
        heights.append(height)
    return ReliefFacts(
        elevation_mean=fsum(heights) / len(heights),
        # Exact flatness only; no undocumented variance/lowland threshold.
        elevation_plain=min(heights) == max(heights) if len(heights) > 1 else None,
    )
