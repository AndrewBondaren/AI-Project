"""One pre-placement allocation in fine² (GEO-1 §5.2-D/§6.29-E)."""

from decimal import Decimal

from pydantic import TypeAdapter

from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterFraction
from app.dataModel.terrain.designedWater.coverage.budget import (
    BodyCoverageAllocation, BodyCoverageRequest, FineArea, WaterCoverageBudget,
)
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent

_AREA = TypeAdapter(FineArea)
_REQUESTS = TypeAdapter(tuple[BodyCoverageRequest, ...])


def _rounded_area(fraction: WaterFraction, area: FineArea) -> int:
    # Exact half-up arithmetic from the canonical decimal, independent of the
    # process Decimal precision and of binary-float multiplication rounding.
    numerator, denominator = Decimal(str(fraction)).as_integer_ratio()
    return (2 * numerator * area + denominator) // (2 * denominator)


class WaterCoverageBudgetPolicy:
    def calculate(self, world_extent: TerrainRegionExtent,
                  world_context: ResolvedWaterGenerationContext,
                  body_requests: tuple[BodyCoverageRequest, ...], *,
                  authored_union_fine2: FineArea,
                  available_auto_area_fine2: FineArea) -> WaterCoverageBudget:
        """Allocate the supplied union cap; do not measure geometry or resolve policy."""
        if not isinstance(world_extent, TerrainRegionExtent):
            raise TypeError("world_extent requires a terrain-owned extent")
        if not isinstance(world_context, ResolvedWaterGenerationContext):
            raise TypeError("world_context requires an immutable resolved cascade result")
        if not isinstance(body_requests, tuple) or any(not isinstance(r, BodyCoverageRequest) for r in body_requests):
            raise TypeError("body_requests requires a tuple of typed coverage requests")
        extent = TerrainRegionExtent.model_validate(world_extent, strict=True)
        context = ResolvedWaterGenerationContext.model_validate(world_context, strict=True)
        requests = _REQUESTS.validate_python(body_requests, strict=True)
        authored = _AREA.validate_python(authored_union_fine2, strict=True)
        available = _AREA.validate_python(available_auto_area_fine2, strict=True)
        area = extent.generation_area_fine2
        if context.level is not WaterGenerationScope.WORLD:
            raise ValueError("world budget requires world-scope resolved context")
        if authored > area or available > area - authored:
            raise ValueError("supplied union areas exceed world fine² area")
        if len({r.source_uid for r in requests}) != len(requests):
            raise ValueError("duplicate source coverage request")
        region_areas = {extent.region_uid: area}
        for request in requests:
            previous = region_areas.setdefault(request.generation_region_uid, request.generation_area_fine2)
            if previous != request.generation_area_fine2 or request.generation_area_fine2 > area:
                raise ValueError("generation region area disagrees with terrain extent identity")

        target = _rounded_area(context.water_fraction, area)
        residual = max(0, target - authored)
        ordered = tuple(sorted(requests, key=lambda r: r.source_uid))
        requested = tuple(_rounded_area(r.target_fraction, r.generation_area_fine2) for r in ordered)
        total = sum(requested)
        cap = min(residual, available, total)
        shares = tuple(divmod(cap * amount, total) if total else (0, 0) for amount in requested)
        remaining = cap - sum(whole for whole, _ in shares)
        winners = frozenset(sorted(range(len(ordered)),
            key=lambda i: (-shares[i][1], ordered[i].source_uid))[:remaining])
        allocations = tuple(BodyCoverageAllocation(
            source_uid=request.source_uid, generation_region_uid=request.generation_region_uid,
            requested_fine2=requested[i], allocated_fine2=shares[i][0] + (1 if i in winners else 0),
        ) for i, request in enumerate(ordered))
        return WaterCoverageBudget(
            region_uid=extent.region_uid, area_fine2=area, target_fraction=context.water_fraction,
            target_fine2=target, authored_union_fine2=authored, residual_fine2=residual,
            allocations=allocations,
        )
