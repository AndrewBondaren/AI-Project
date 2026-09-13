"""Pack L2 city ASCII — FineTerrain at world-z + outdoor shell from settlement.zst.

Does not mutate ``surface``. Empty city z are omitted (occupied z only).
"""

from __future__ import annotations

from app.application.worldData.pack.read.settlementStructureIndex import index_shell_cells
from app.application.worldData.render.fineTerrainAsciiKernel import (
    draw_symbol_grid,
    symbols_at_z,
)
from app.application.worldData.render.mapSymbols import symbol_for_role_or_terrain
from app.application.worldData.render.renderPayloads import city_level_key
from app.application.worldData.render.structureAsciiSymbols import (
    render_structure_legend,
    symbol_for_building_element,
)
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire
from app.dataModel.worldPack.settlementStructureWire import SettlementStructureWire, ShellCellWire
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


class LocationCityPackRenderer:
    """Composite outdoor city over location FineTerrain, one ASCII field per occupied z."""

    def __init__(
        self,
        chunk: FineTerrainChunkWire,
        *,
        volume: TerritoryVolume,
        location_uid: str,
        wire: SettlementStructureWire,
    ) -> None:
        self._chunk = chunk
        self._volume = volume
        self.location_uid = location_uid
        self._cols: dict[tuple[int, int], FineTerrainColumnWire] = {
            (c.lx, c.ly): c for c in chunk.columns
        }
        self._index = index_shell_cells(wire)

    @staticmethod
    def render_legend() -> str:
        return render_structure_legend()

    def _world_xy(self, lx: int, ly: int) -> tuple[int, int]:
        return self._volume.x0 + lx, self._volume.y0 + ly

    def _local_xy(self, x: int, y: int) -> tuple[int, int]:
        return x - self._volume.x0, y - self._volume.y0

    def _col_bounds(self) -> tuple[int, int, int, int] | None:
        if not self._cols:
            return None
        xs = [x for x, _ in self._cols]
        ys = [y for _, y in self._cols]
        return min(xs), max(xs), min(ys), max(ys)

    def _city_bounds(self) -> tuple[int, int, int, int] | None:
        if not self._index:
            return None
        locals_xy = [self._local_xy(x, y) for (x, y, _z) in self._index]
        xs = [x for x, _ in locals_xy]
        ys = [y for _, y in locals_xy]
        return min(xs), max(xs), min(ys), max(ys)

    def _frame_bounds(self) -> tuple[int, int, int, int] | None:
        return self._col_bounds() or self._city_bounds()

    def _extra_headers(self, lx0: int, ly0: int, lx1: int, ly1: int) -> list[str]:
        wx0, wy0 = self._world_xy(lx0, ly0)
        wx1, wy1 = self._world_xy(lx1, ly1)
        vol = self._volume
        return [
            (
                f"territory meters x: {vol.x0}..{vol.x1}  y: {vol.y0}..{vol.y1}  "
                f"z: {vol.z0}..{vol.z1}"
            ),
            f"world meters x: {wx0}..{wx1 + 1}  y: {wy0}..{wy1 + 1}",
        ]

    def occupied_city_z(self) -> list[int]:
        return sorted({z for (_x, _y, z) in self._index})

    def _shell_symbol(self, cell: ShellCellWire) -> str:
        if cell.system_building_element:
            return symbol_for_building_element(
                cell.system_building_element,
                facing=cell.system_facing,
            )
        return symbol_for_role_or_terrain(system_terrain=cell.system_terrain)

    def _overlay_at_z(self, z: int) -> dict[tuple[int, int], str]:
        want = int(z)
        out: dict[tuple[int, int], str] = {}
        frame = self._frame_bounds()
        for (x, y, cz), cell in self._index.items():
            if int(cz) != want:
                continue
            lx, ly = self._local_xy(x, y)
            if frame is not None:
                x0, x1, y0, y1 = frame
                if lx < x0 or lx > x1 or ly < y0 or ly > y1:
                    continue
            out[(lx, ly)] = self._shell_symbol(cell)
        return out

    def render_at_z(self, z: int) -> str:
        overlay = self._overlay_at_z(z)
        if not overlay:
            return ""
        symbols = dict(symbols_at_z(self._cols, int(z)))
        symbols.update(overlay)
        bounds = self._frame_bounds()
        if bounds is None:
            return ""
        x0, x1, y0, y1 = bounds
        return draw_symbol_grid(
            symbols,
            title=(
                f"location={self.location_uid} city z={int(z)}  "
                f"(pack settlement + location_terrain at z)"
            ),
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="local ",
            bounds=bounds,
        )

    def render_all_city_levels(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for z in self.occupied_city_z():
            text = self.render_at_z(z)
            if text.strip():
                out[city_level_key(z)] = text
        return out
