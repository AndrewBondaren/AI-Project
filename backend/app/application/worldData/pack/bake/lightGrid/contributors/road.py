"""Road contributor — world ConnectionEdge → road terrain (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import (
    dilate,
    light_polyline_from_meters,
)
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain
from app.db.models.namedLocation import NamedLocation

logger = logging.getLogger(__name__)


def _node_meters(
    node_uid: str,
    nodes_by_uid: dict,
    locations_by_uid: dict[str, NamedLocation],
) -> tuple[int, int] | None:
    node = nodes_by_uid.get(node_uid)
    if node is None:
        return None
    if node.location_uid and node.location_uid in locations_by_uid:
        loc = locations_by_uid[node.location_uid]
        x = loc.map_x if loc.map_x is not None else node.x
        y = loc.map_y if loc.map_y is not None else node.y
        return int(x), int(y)
    return int(node.x), int(node.y)


class RoadContributor:
    name = "road"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        masks = terrain_masks(ctx.world)
        policy = masks.default_roads
        if not masks.category_enabled(policy):
            logger.debug(
                "light_contributor_road | world=%s skipped=disabled",
                ctx.world.world_uid,
            )
            return
        if not ctx.edges or not ctx.nodes:
            logger.debug(
                "light_contributor_road | world=%s skipped=no_graph",
                ctx.world.world_uid,
            )
            return

        scale = compose.scale
        tile_set = set(ctx.tiles)
        nodes_by_uid = {n.node_uid: n for n in ctx.nodes}
        locations_by_uid = {loc.location_uid: loc for loc in ctx.locations}
        type_set = set(policy.connection_types)
        level_set = set(policy.graph_levels)
        painted = 0
        edges_used = 0

        for edge in ctx.edges:
            if edge.connection_type not in type_set:
                continue
            if edge.graph_level not in level_set:
                continue
            a = _node_meters(edge.from_node_uid, nodes_by_uid, locations_by_uid)
            b = _node_meters(edge.to_node_uid, nodes_by_uid, locations_by_uid)
            if a is None or b is None:
                continue
            light_cells = set(light_polyline_from_meters([a, b], scale))
            if policy.dilate_radius_light > 0:
                light_cells = dilate(light_cells, int(policy.dilate_radius_light))
            n = paint_system_terrain(
                compose,
                light_cells,
                policy.system_terrain,
                masks=masks,
                tile_set=tile_set,
                preserve_hydro=True,
            )
            if n:
                edges_used += 1
                painted += n

        logger.debug(
            "light_contributor_road | world=%s edges_used=%d cells_painted=%d",
            ctx.world.world_uid,
            edges_used,
            painted,
        )
