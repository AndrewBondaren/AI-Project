"""Raster authored city shell into WP-20 merge — tz_settlement_outdoor C12."""

from __future__ import annotations

from collections import OrderedDict

from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.dataModel.worldPack.mergeMapCells import CellContribution
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy
from app.dataModel.worldPack.settlementStructureWire import (
    SettlementStructureWire,
    ShellCellWire,
)
from app.db.models.world import World


def _index_shell_cells(wire: SettlementStructureWire) -> dict[tuple[int, int, int], ShellCellWire]:
    index: dict[tuple[int, int, int], ShellCellWire] = {}

    def put_all(cells: list[ShellCellWire]) -> None:
        for cell in cells:
            index[(cell.x, cell.y, cell.z)] = cell

    put_all(list(wire.barrier_cells))
    for district in wire.districts:
        put_all(list(district.barrier_cells))
        for area in district.areas:
            put_all(list(area.yard_cells))
            put_all(list(area.barrier_cells))
            for small in area.small_layouts:
                put_all(list(small))
            for building in area.buildings:
                put_all(list(building.shell_cells))
    return index


class SettlementStructureRaster:
    def __init__(self, context: PackReadContext) -> None:
        self._ctx = context
        policy = PackReadPolicy.canonical_defaults()
        self._cap = policy.settlement_structure_lru_capacity
        self._index_cache: OrderedDict[str, dict[tuple[int, int, int], ShellCellWire]] = OrderedDict()

    def invalidate(self) -> None:
        self._index_cache.clear()

    def contribution(self, world: World, x: int, y: int, z: int) -> CellContribution | None:
        if not self._ctx.has_pack_for(world):
            return None
        manifest = self._ctx.reader_for(world).manifest
        for entry in manifest.settlement_structure_entries:
            if not entry.structure_path or not entry.territory_volume.contains(x, y, z):
                continue
            try:
                index = self._index_for(world, entry.location_uid)
            except FileNotFoundError:
                continue
            cell = index.get((x, y, z))
            if cell is None:
                continue
            return CellContribution(
                x=cell.x,
                y=cell.y,
                z=cell.z,
                system_terrain=cell.system_terrain,
                system_material=cell.system_material,
                system_building_element=cell.system_building_element,
                is_structural=cell.is_structural,
                location_uid=cell.location_uid,
            )
        return None

    def _index_for(
        self, world: World, location_uid: str,
    ) -> dict[tuple[int, int, int], ShellCellWire]:
        cache_key = f"{self._ctx.paths_for(world).root}:{location_uid}"
        cached = self._index_cache.get(cache_key)
        if cached is not None:
            self._index_cache.move_to_end(cache_key)
            return cached
        wire = self._ctx.reader_for(world).read_settlement_structure(location_uid)
        index = _index_shell_cells(wire)
        self._index_cache[cache_key] = index
        if len(self._index_cache) > self._cap:
            self._index_cache.popitem(last=False)
        return index
