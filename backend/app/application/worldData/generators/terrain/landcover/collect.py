"""Resolve anchors/state after the shared source merge, without persistence."""

from dataclasses import replace
import logging

from app.application.worldData.generators.terrain.landcover.types import LandcoverInputs, ResolvedRegion
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.regions.coverageResolver import resolve
from app.dataModel.spatial.regionShape import AnchorRadiusShape, EllipseShape
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

logger = logging.getLogger(__name__)


def resolve_collected(regions: list[ResolvedRegion], ctx: LightGridBakeContext,
                      inputs: LandcoverInputs, registry: WorldTerrainRegistry) -> list[ResolvedRegion]:
    locations = {loc.location_uid: loc for loc in ctx.locations}
    resolved = []
    for region in regions:
        state = inputs.state_snapshot.get(region.region_uid)
        if state is not None and state.tombstone:
            logger.debug("landcover | collect_tombstone | region_uid=%s", region.region_uid)
            continue
        if state is not None:
            region = replace(region, current_type=state.current_type)
        if registry.entry_for(region.current_type) is None:
            logger.warning("landcover | collect_unresolved | WarningError | region_uid=%s reason=unknown_terrain key=%s",
                           region.region_uid, region.current_type)
            continue
        shape = region.spec.shape
        if isinstance(shape, AnchorRadiusShape):
            anchor = locations.get(shape.anchor_uid)
            if anchor is None or anchor.map_x is None or anchor.map_y is None:
                logger.warning("landcover | collect_unresolved | WarningError | region_uid=%s reason=missing_anchor anchor_uid=%s",
                               region.region_uid, shape.anchor_uid)
                continue
            shape = EllipseShape(cx=anchor.map_x, cy=anchor.map_y, rx=shape.radius, ry=shape.radius,
                                 edge_noise=shape.edge_noise)
            region = replace(region, spec=region.spec.model_copy(update={"shape": shape}))
        if region.claim is None and region.current_type == registry.forest_terrain_key():
            # Same eligibility contract as autoresolve; only diagnostics here, never a veto.
            x_min, y_min, x_max, y_max = shape.bbox()
            facts = inputs.facts_at(((x_min + x_max) // 2, (y_min + y_max) // 2))
            forest = registry.entry_for(region.current_type)
            if resolve(facts, WorldTerrainRegistry([forest])) is None:
                logger.warning("landcover | declared_without_suitability | region_uid=%s entry_type=%s",
                               region.region_uid, region.current_type)
        resolved.append(region)
    return resolved
