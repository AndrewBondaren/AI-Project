"""In-memory L0 light-grid canvas — tz_map_light_bake."""

from __future__ import annotations

from collections.abc import Iterator

from app.application.worldData.pack.bake.lightGrid.cell import LightGridCell
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


class LightGridCompose:
    def __init__(self, scale: LightGridScale) -> None:
        self.scale = scale
        self._cells: dict[tuple[int, int, int, int], LightGridCell] = {}

    @property
    def side(self) -> int:
        return self.scale.side

    @property
    def tile_m(self) -> int:
        return self.scale.tile_m

    @property
    def light_m(self) -> int:
        return self.scale.light_m

    def ensure(self, gx: int, gy: int, tx: int, ty: int) -> LightGridCell:
        key = (gx, gy, tx, ty)
        cell = self._cells.get(key)
        if cell is None:
            cell = LightGridCell.from_wire_defaults()
            self._cells[key] = cell
        return cell

    def get(self, gx: int, gy: int, tx: int, ty: int) -> LightGridCell | None:
        return self._cells.get((gx, gy, tx, ty))

    def iter_tile(self, gx: int, gy: int) -> Iterator[tuple[int, int, LightGridCell]]:
        side = self.side
        for ty in range(side):
            for tx in range(side):
                cell = self._cells.get((gx, gy, tx, ty))
                if cell is not None:
                    yield tx, ty, cell

    def to_wire_tile(self, gx: int, gy: int) -> list[WorldMapCellWire]:
        side = self.side
        out: list[WorldMapCellWire] = []
        default = LightGridCell.from_wire_defaults()
        for ty in range(side):
            for tx in range(side):
                cell = self._cells.get((gx, gy, tx, ty), default)
                out.append(cell.to_wire(tx, ty))
        return out

    def ensure_tile(self, gx: int, gy: int) -> None:
        side = self.side
        for ty in range(side):
            for tx in range(side):
                self.ensure(gx, gy, tx, ty)
