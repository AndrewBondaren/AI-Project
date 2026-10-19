"""CoverageResolver owns seed kinds; RegionRasterizer owns claim geometry."""

from collections.abc import Callable
from collections import Counter

from app.application.worldData.generators.terrain.landcover.autoresolve.mergeSublocations import CoverageSeed, merge_sublocations
from app.application.worldData.generators.terrain.landcover.autoresolve.seedGrid import WorldSeed, generate_seeds
from app.application.worldData.generators.terrain.landcover.types import LandcoverInputs, RegionSource, ResolvedRegion
from app.application.worldData.masks.regionRasterContext import (
    ClaimSeed, RegionClaim, fine_topology,
)
from app.application.worldData.masks.regionRasterizer import ClaimOwnersIndex
from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.regionFacts import RegionFacts
from app.dataModel.spatial.regionShape import BboxShape, Point
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.regions import RegionSpecBase


def resolve_seeds(seeds: tuple[WorldSeed, ...], facts_at: Callable[[Point], RegionFacts],
                  registry: WorldTerrainRegistry) -> tuple[CoverageSeed, ...]:
    resolved = []
    for seed in seeds:
        target = resolve(facts_at(seed.coord), registry)
        if target is not None:
            resolved.append(CoverageSeed(seed, target.target_key))
    return tuple(resolved)


def autoresolve_regions(world_uid: str, root: str, tile_macro: int, inputs: LandcoverInputs,
                        policy: LandcoverRegionsCategoryPolicy,
                        registry: WorldTerrainRegistry) -> tuple[list[ResolvedRegion], ClaimOwnersIndex]:
    topology = fine_topology(inputs.topology, tile_macro)
    seeds = resolve_seeds(generate_seeds(root, topology, policy), inputs.facts_at, registry)
    regions = merge_sublocations(seeds, topology, policy, world_uid)
    claim = RegionClaim(tuple(ClaimSeed(seed.seed.coord, region.region_uid)
                              for region in regions for seed in region.seeds),
                       policy.max_radius, policy.claim_noise)
    # Area of the source graph geometry (unit fine-cell squares), independent
    # of L0 resolution, density and requested bake tiles. Never the envelope area.
    index = ClaimOwnersIndex(claim, root, topology)
    areas = Counter(seed.region_uid for seed in index.owners.values())
    bounds = topology.bounds
    # Resolved geometric envelope only: actual membership is the shared claim predicate.
    envelope = BboxShape(x_min=bounds.x_min, y_min=bounds.y_min,
                         x_max=bounds.x_max, y_max=bounds.y_max)
    return [ResolvedRegion(world_uid, region.region_uid, RegionSpecBase(shape=envelope),
                            region.target_key, RegionSource.AUTORESOLVE, inputs.topology,
                            claim, region.sublocations, float(areas[region.region_uid]), entry_type=region.target_key) for region in regions], index
