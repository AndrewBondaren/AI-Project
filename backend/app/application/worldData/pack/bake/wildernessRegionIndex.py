"""Pure adapter: resolved collect results → canonical fine-coordinate index."""
from collections.abc import Iterable

from app.application.worldData.generators.terrain.landcover.types import RegionSource, ResolvedRegion
from app.application.worldData.generators.terrain.landcover.regionIdentityCheck import require_unique_region_uids
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import claim_owners
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.worldPack.meta.wildernessRegionEntry import (
    RegionIndexBounds, WildernessRegionEntry, WildernessRegionStatus, require_region_index,
)
from app.ids import seed_root
from app.application.worldData.generators.terrain.landcover.regionRevision import region_fingerprint
from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.terrain.landcover.regionCoverageValidation import validate_region_coverage
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

_STATUS = {RegionSource.DECLARED: WildernessRegionStatus.DECLARED,
           RegionSource.ANCHOR: WildernessRegionStatus.ANCHOR,
           RegionSource.AUTORESOLVE: WildernessRegionStatus.AUTORESOLVED}


def _bounds(coords: Iterable[tuple[int, int]]) -> RegionIndexBounds | None:
    points = iter(coords)
    first = next(points, None)
    if first is None:
        return None
    x0 = x1 = first[0]
    y0 = y1 = first[1]
    for x, y in points:
        x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return RegionIndexBounds(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


def _shape_bounds(region: ResolvedRegion, ctx: RegionRasterContext) -> RegionIndexBounds | None:
    x0, y0, x1, y1 = region.spec.shape.bbox()
    topology = ctx.fine_topology()
    b = topology.bounds
    raw = ((x0,y0),(x0,y1),(x1,y0),(x1,y1))
    # A single AABB conservatively encloses disjoint canonical seam parts.
    if any((canonical := topology.canonicalize(*p)) is not None and canonical != p for p in raw):
        return RegionIndexBounds(x_min=b.x_min,y_min=b.y_min,x_max=b.x_max,y_max=b.y_max)
    x0,y0,x1,y1 = max(x0,b.x_min),max(y0,b.y_min),min(x1,b.x_max),min(y1,b.y_max)
    return RegionIndexBounds(x_min=x0,y_min=y0,x_max=x1,y_max=y1) if x0 <= x1 and y0 <= y1 else None



def _claim_bounds(owners):
    """One pass over a shared claim, rather than scanning the world for each seed."""
    roots, seeds = {}, {}
    for (x,y), owner in owners.items():
        for target, key in ((roots,owner.region_uid),(seeds,(owner.region_uid,owner.coord))):
            previous = target.get(key)
            target[key] = (x,y,x,y) if previous is None else (
                min(previous[0],x),min(previous[1],y),max(previous[2],x),max(previous[3],y))
    def boxes(values):
        return {key: RegionIndexBounds(x_min=b[0],y_min=b[1],x_max=b[2],y_max=b[3])
                for key,b in values.items()}
    return boxes(roots),boxes(seeds)


def build_region_index(regions: list[ResolvedRegion], scale: LightGridScale, *,
                       registry: WorldTerrainRegistry) -> list[WildernessRegionEntry]:
    regions = [validate_region_coverage(region, registry, ctx=ResolveContext(
        path_prefix=(region.world_uid, "wilderness_region_entries", index)))
        for index, region in enumerate(regions)]
    require_unique_region_uids(regions)
    entries: list[WildernessRegionEntry] = []
    claims: dict[int, tuple[dict, dict]] = {}
    for region in regions:
        ctx = RegionRasterContext(region.region_uid, region.spec, scale, region.topology)
        seed_boxes = {}
        if region.claim is not None:
            key = id(region.claim)
            if key not in claims:
                claims[key] = _claim_bounds(claim_owners(region.claim, seed_root(region), ctx.fine_topology()))
            root_boxes,seed_boxes = claims[key]
            bbox = root_boxes.get(region.region_uid)
        else:
            bbox = _shape_bounds(region, ctx)
        if bbox is None:
            continue
        fingerprint = region_fingerprint(region)
        entries.append(WildernessRegionEntry(region_uid=region.region_uid, entry_type=region.entry_type,
            current_type=region.current_type, bbox=bbox, status=_STATUS[region.source],
            spec_fingerprint=fingerprint))
        for sub in region.sublocations:
            sub_bbox = seed_boxes.get((region.region_uid,sub.seed_xy))
            if sub_bbox is None:
                # A seed remains an addressable part even if claim competition leaves it empty.
                coord = ctx.fine_topology().canonicalize(*sub.seed_xy)
                if coord is None:
                    raise ValueError("sublocation seed is outside world topology")
                sub_bbox = _bounds([coord])
            entries.append(WildernessRegionEntry(region_uid=sub.region_uid, entry_type=region.entry_type,
                current_type=region.current_type, bbox=sub_bbox, status=WildernessRegionStatus.SUBLOCATION,
                parent_region_uid=region.region_uid, spec_fingerprint=fingerprint))
    require_region_index(entries)
    return sorted(entries, key=lambda e: e.region_uid)
