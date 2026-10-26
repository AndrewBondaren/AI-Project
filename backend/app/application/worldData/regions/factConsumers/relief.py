"""Relief-only elevation observations (before hydrology carve)."""

from math import fsum

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ReliefFacts


def contribute(context: FactConsumerContext) -> ReliefFacts | None:
    if context.terrain is None or not context.cells:
        return None
    surface_z = context.terrain.relief_z
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
