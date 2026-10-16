"""Patch store backed by map_cell_patches."""

from __future__ import annotations

from app.application.worldData.pack.read.patchCellContribution import map_cell_to_patch_contribution
from app.dataModel.worldPack.mergeMapCells import CellContribution
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository


class PatchStoreService:
    def __init__(self, repo: IMapCellRepository | None = None) -> None:
        self._repo = repo

    async def get_patches_in_bbox(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[CellContribution]:
        if self._repo is None:
            return []
        cells = await self._repo.get_z_slice(
            world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )
        return [
            contrib
            for c in cells
            if (contrib := map_cell_to_patch_contribution(c)).has_data()
        ]

    async def get_patches_map_in_bbox(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> dict[tuple[int, int, int], CellContribution]:
        patches = await self.get_patches_in_bbox(
            world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )
        return {(p.x, p.y, p.z): p for p in patches}

    async def get_patch_at(
        self,
        world_uid: str,
        x: int,
        y: int,
        z: int,
    ) -> CellContribution | None:
        if self._repo is None:
            return None
        cells = await self._repo.get_z_slice(world_uid, x, x, y, y, z, z)
        if not cells:
            return None
        contrib = map_cell_to_patch_contribution(cells[0])
        return contrib if contrib.has_data() else None

    async def get_all_patches(self, world_uid: str) -> list[CellContribution]:
        if self._repo is None:
            return []
        cells = await self._repo.get_by_world(world_uid)
        return [
            contrib
            for cell in cells
            if (contrib := map_cell_to_patch_contribution(cell)).has_data()
        ]

    async def upsert_patch(self, cell: MapCell) -> None:
        if self._repo is None:
            raise RuntimeError("PatchStoreService has no repository")
        await self._repo.upsert(cell)
