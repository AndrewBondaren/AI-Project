"""Relief-only elevation observations (before hydrology carve)."""

from math import fsum

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ReliefFacts


def contribute(context: FactConsumerContext) -> ReliefFacts | None:
    if context.surface is None or not context.cells:
        return None
    heights = [context.surface.coarse_relief_z.get(cell) for cell in sorted(set(context.cells))]
    if any(height is None for height in heights):
        return None
    return ReliefFacts(
        elevation_mean=fsum(heights) / len(heights),
        # Exact flatness only; no undocumented variance/lowland threshold.
        elevation_plain=min(heights) == max(heights) if len(heights) > 1 else None,
    )
