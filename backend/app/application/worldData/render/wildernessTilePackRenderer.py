"""Pack-native wilderness L2 ASCII — mosaic of ``r.{gx}.{gy}.c.{cx}.{cy}.zst`` chunks."""

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


class WildernessTilePackRenderer:
    """L2 wilderness for one macro-tile — tile-local meter keys from chunk (cx,cy,lx,ly)."""

    def __init__(
        self,
        chunks: list[FineTerrainChunkWire],
        *,
        tile_gx: int,
        tile_gy: int,
        tile_size_m: int,
    ) -> None:
        self.tile_gx = tile_gx
        self.tile_gy = tile_gy
        self.tile_size_m = tile_size_m
        self._cols: dict[tuple[int, int], FineTerrainColumnWire] = {}
        for chunk in chunks:
            cc = max(1, int(chunk.chunk_columns))
            for col in chunk.columns:
                tx = chunk.cx * cc + col.lx
                ty = chunk.cy * cc + col.ly
                self._cols[(tx, ty)] = col

    @staticmethod
    def render_legend() -> str:
        return render_map_legend(mark_location=False)

    @property
    def column_count(self) -> int:
        return len(self._cols)

    def _world_xy(self, tx: int, ty: int) -> tuple[int, int]:
        return (
            self.tile_gx * self.tile_size_m + tx,
            self.tile_gy * self.tile_size_m + ty,
        )

    def _extra_headers(self, tx0: int, ty0: int, tx1: int, ty1: int) -> list[str]:
        wx0, wy0 = self._world_xy(tx0, ty0)
        wx1, wy1 = self._world_xy(tx1, ty1)
        return [
            (
                f"macro-tile=({self.tile_gx},{self.tile_gy})  "
                f"tile_size_m={self.tile_size_m}  columns={self.column_count}"
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
            coord_prefix="tile-local ",
        )

    def render_surface_top(self) -> str:
        if not self._cols:
            return ""
        return self._draw(
            symbols_surface_top(self._cols),
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"(pack wilderness_chunk mosaic, top z)"
            ),
        )

    def render_level(self, z: int) -> str:
        if not self._cols:
            return ""
        level = symbols_at_z(self._cols, z)
        if not level:
            return ""
        return self._draw(
            level,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                f"(pack wilderness_chunk mosaic)"
            ),
        )

    def z_levels(self) -> list[int]:
        return z_endpoints(self._cols.values())

    def render_all_levels(self, *, include_z_slices: bool = True) -> dict[str, str]:
        """Keys: ``LEVEL_SURFACE``; optional decimal world-z run endpoints."""
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        if not include_z_slices:
            return out
        for z in self.z_levels():
            text = self.render_level(z)
            if text.strip():
                out[str(z)] = text
        return out
