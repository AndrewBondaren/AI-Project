"""Debug ASCII map render orchestration — pack vs legacy collaborators."""

from __future__ import annotations

from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.render.legacyMapGridRender import LegacyMapGridRender
from app.application.worldData.render.packMapGridRender import PackMapGridRender
from app.db.models.world import World


class MapGridRenderService:
    def __init__(self, map_cell_service: MapCellService) -> None:
        self._map_cells = map_cell_service
        self._legacy = LegacyMapGridRender(map_cell_service)

    def _pack(self, world: World) -> PackMapGridRender | None:
        pack = self._map_cells.pack_read_services(world)
        if pack is None:
            return None
        return PackMapGridRender(pack.render)

    async def render_world_grid(
        self,
        world: World,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_locations: bool = True,
    ) -> dict[str, object]:
        pack = self._pack(world)
        if pack is not None:
            return pack.render_world_grid(
                world,
                gx0=gx0,
                gy0=gy0,
                gx1=gx1,
                gy1=gy1,
                mark_locations=mark_locations,
            ).to_dict()
        return (
            await self._legacy.render_world_grid(
                world,
                gx0=gx0,
                gy0=gy0,
                gx1=gx1,
                gy1=gy1,
                mark_locations=mark_locations,
            )
        ).to_dict()

    async def render_world_tile_grids(self, world: World) -> dict[str, object]:
        pack = self._pack(world)
        if pack is not None:
            return pack.render_world_tile_grids(world).to_dict()
        return (await self._legacy.render_world_tile_grids(world)).to_dict()

    async def render_all_location_grids(self, world: World) -> dict[str, object]:
        pack = self._pack(world)
        if pack is not None:
            return pack.render_all_location_grids(world).to_dict()
        return (await self._legacy.render_all_location_grids(world)).to_dict()

    async def render_location_grid(
        self,
        world: World,
        location_uid: str,
        *,
        z: int | None = None,
    ) -> dict[str, object]:
        pack = self._pack(world)
        if pack is not None:
            return pack.render_location_grid(world, location_uid, z=z).to_dict()
        return (await self._legacy.render_location_grid(world, location_uid, z=z)).to_dict()
