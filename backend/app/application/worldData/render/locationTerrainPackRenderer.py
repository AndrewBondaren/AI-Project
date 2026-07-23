"""Pack-native location terrain ASCII — ``l.{uid}.terrain.zst`` (FineTerrainChunkWire)."""

from __future__ import annotations

from app.application.worldData.render.fineTerrainAsciiKernel import (
    draw_symbol_grid,
    symbols_at_z,
    symbols_surface_top,
    z_endpoints,
)
from app.application.worldData.render.mapSymbols import render_map_legend
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


class LocationTerrainPackRenderer:
    """L2 location terrain from pack blob — local (lx,ly) + absolute world z."""

    def __init__(
        self,
        chunk: FineTerrainChunkWire,
        *,
        volume: TerritoryVolume,
        location_uid: str,
    ) -> None:
        self._chunk = chunk
        self._volume = volume
        self.location_uid = location_uid
        self._cols: dict[tuple[int, int], FineTerrainColumnWire] = {
            (c.lx, c.ly): c for c in chunk.columns
        }

    @staticmethod
    def render_legend() -> str:
        return render_map_legend(mark_location=False)

    def _world_xy(self, lx: int, ly: int) -> tuple[int, int]:
        return self._volume.x0 + lx, self._volume.y0 + ly

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

    def _draw(self, symbols: dict[tuple[int, int], str], *, title: str) -> str:
        if not symbols:
            return ""
        xs = [x for x, _ in symbols]
        ys = [y for _, y in symbols]
        return draw_symbol_grid(
            symbols,
            title=title,
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys)),
            coord_prefix="local ",
        )

    def render_surface_top(self) -> str:
        if not self._cols:
            return ""
        return self._draw(
            symbols_surface_top(self._cols),
            title=f"location={self.location_uid}  (pack location_terrain, top z)",
        )

    def render_level(self, z: int) -> str:
        if not self._cols:
            return ""
        level = symbols_at_z(self._cols, z)
        if not level:
            return ""
        return self._draw(
            level,
            title=f"location={self.location_uid} z={z}  (pack location_terrain)",
        )

    def z_levels(self) -> list[int]:
        return z_endpoints(self._cols.values())

    def render_all_levels(self) -> dict[str, str]:
        """Keys: ``LEVEL_SURFACE`` plus decimal world-z run endpoints."""
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        for z in self.z_levels():
            text = self.render_level(z)
            if text.strip():
                out[str(z)] = text
        return out
