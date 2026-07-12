"""Hydrology generator orchestrator — D HY-2."""

from __future__ import annotations

import logging

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.hydrology.basins.coastalLandformClassifier import (
    classify_coastal_landforms,
)
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    seas_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralSeaAutoresolve import (
    autoresolve_sea_basins,
)
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import (
    generate_lakes,
)
from app.application.worldData.generators.hydrology.basins.oceanBasinGenerator import (
    generate_open_ocean,
)
from app.application.worldData.generators.hydrology.rivers.riverBedCarver import generate_rivers
from app.application.worldData.generators.hydrology.basins.seaBasinGenerator import (
    generate_coastal_sea,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    HydrologyResult,
    HydrologyScope,
    resolve_scopes,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _merge_bbox(a: GridBBox | None, b: GridBBox | None) -> GridBBox | None:
    if a is None:
        return b
    if b is None:
        return a
    return GridBBox(
        min(a.x_min, b.x_min),
        max(a.x_max, b.x_max),
        min(a.y_min, b.y_min),
        max(a.y_max, b.y_max),
    )


class HydrologyGeneratorService:
    """Pure generator — mutates heightmap surface_z + cell_index roles."""

    def apply(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap: SurfaceHeightmap,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        scopes: frozenset[HydrologyScope] | None = None,
        master: HydrologyMasterInput | None = None,
    ) -> HydrologyResult:
        nodes = nodes or []
        edges = edges or []
        inp = master or build_hydrology_master_input(
            world, locations, nodes, edges, scopes=scopes,
        )

        if not inp.hydrology_enabled:
            logger.debug("HydrologyGeneratorService | skip disabled world=%s", world.world_uid)
            return HydrologyResult(heightmap=heightmap)

        active = resolve_scopes(inp.scopes)
        result = HydrologyResult(heightmap=heightmap)
        dirty: GridBBox | None = None

        if HydrologyScope.COASTAL_SEA in active:
            coastal, bbox = generate_coastal_sea(world, heightmap, inp)
            result.cell_index.by_cell.update(coastal)
            dirty = _merge_bbox(dirty, bbox)
            logger.info(
                "HydrologyGeneratorService | coastal_sea world=%s cells=%d segments=%d",
                world.world_uid,
                len(coastal),
                len(inp.declared_coastline_segments),
            )

            seas_policy = seas_autoresolve_policy(world)
            if seas_policy.seas_enabled and (
                seas_policy.autoresolve_coastal_sea or seas_policy.autoresolve_open_ocean
            ):
                auto, auto_bbox = autoresolve_sea_basins(
                    world,
                    heightmap,
                    inp,
                    result.cell_index.by_cell,
                    autoresolve_coastal=seas_policy.autoresolve_coastal_sea,
                    autoresolve_open_ocean=seas_policy.autoresolve_open_ocean,
                )
                result.cell_index.by_cell.update(auto)
                dirty = _merge_bbox(dirty, auto_bbox)
                logger.info(
                    "HydrologyGeneratorService | autoresolve_sea world=%s cells=%d",
                    world.world_uid,
                    len(auto),
                )

        if HydrologyScope.OPEN_OCEAN in active:
            ocean, bbox = generate_open_ocean(heightmap, result.cell_index.by_cell)
            result.cell_index.by_cell.update(ocean)
            dirty = _merge_bbox(dirty, bbox)
            logger.info(
                "HydrologyGeneratorService | open_ocean world=%s cells=%d",
                world.world_uid,
                len(ocean),
            )

        if HydrologyScope.LAKES in active:
            lakes, bbox = generate_lakes(
                world,
                heightmap,
                inp,
                occupied=result.cell_index.by_cell,
            )
            result.cell_index.by_cell.update(lakes)
            dirty = _merge_bbox(dirty, bbox)
            logger.info(
                "HydrologyGeneratorService | lakes world=%s cells=%d specs=%d",
                world.world_uid,
                len(lakes),
                len(inp.declared_lake_specs),
            )

        if HydrologyScope.RIVERS in active:
            rivers, river_segments, bbox = generate_rivers(
                world,
                heightmap,
                inp,
                occupied=result.cell_index.by_cell,
                locations=locations,
            )
            result.cell_index.by_cell.update(rivers)
            result.river_segments = river_segments
            dirty = _merge_bbox(dirty, bbox)
            logger.info(
                "HydrologyGeneratorService | rivers world=%s cells=%d edges=%d",
                world.world_uid,
                len(rivers),
                len(inp.declared_river_edges),
            )

        if HydrologyScope.LANDFORMS in active:
            result.landforms = classify_coastal_landforms(inp)

        result.dirty_bbox = dirty
        logger.info(
            "HydrologyGeneratorService | world=%s scopes=%s modified=%d",
            world.world_uid,
            sorted(s.value for s in active),
            result.cells_modified,
        )
        return result
