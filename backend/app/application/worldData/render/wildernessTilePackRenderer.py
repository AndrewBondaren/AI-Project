"""Pack-native wilderness L2 ASCII — mosaic of ``r.{gx}.{gy}.c.{cx}.{cy}.zst`` chunks."""

from __future__ import annotations

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    draw_int_grid,
    draw_symbol_grid,
    format_sparse_symbol_cells,
    symbols_at_z,
    symbols_by_occupied_z,
    symbols_surface_top,
    values_cliff_delta,
    values_column_span,
    z_occupied,
)
from app.application.worldData.render.mapSymbols import render_map_legend
from app.application.worldData.render.renderPayloads import (
    LEVEL_CLIFF_DELTA,
    LEVEL_COLUMN_SPAN,
    LEVEL_SURFACE,
)
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
        """Horizontal slice at world-z — only columns whose pack runs cover ``z``."""
        if not self._cols:
            return ""
        level = symbols_at_z(self._cols, z)
        if not level:
            return ""
        return self._draw(
            level,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                f"(pack wilderness_chunk mosaic; cells present in FineTerrain only)"
            ),
        )

    def render_occupied_z_levels(self) -> dict[int, str]:
        """Dense ASCII for every occupied world-z (single-pass). Prefer sparse for dumps."""
        if not self._cols:
            return {}
        by_z = symbols_by_occupied_z(self._cols)
        out: dict[int, str] = {}
        for z in sorted(by_z):
            text = self._draw(
                by_z[z],
                title=(
                    f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                    f"(pack wilderness_chunk mosaic; cells present in FineTerrain only)"
                ),
            )
            if text.strip():
                out[int(z)] = text
        return out

    def render_occupied_z_levels_sparse(self) -> dict[int, str]:
        """``format=sparse_xy`` per occupied world-z — detailed_bake dump default."""
        if not self._cols:
            return {}
        by_z = symbols_by_occupied_z(self._cols)
        out: dict[int, str] = {}
        for z in sorted(by_z):
            cells = by_z[z]
            xs = [x for x, _ in cells]
            ys = [y for _, y in cells]
            text = format_sparse_symbol_cells(
                cells,
                title=(
                    f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                    f"(pack wilderness_chunk mosaic; cells present in FineTerrain only)"
                ),
                extra_headers=self._extra_headers(
                    min(xs), min(ys), max(xs), max(ys),
                ),
            )
            if text.strip():
                out[int(z)] = text
        return out

    def render_column_span(self) -> str:
        """Occupied z-count per column — exposes thin L2 fill vs building-like walls."""
        if not self._cols:
            return ""
        values = values_column_span(self._cols)
        if not values:
            return ""
        xs = [x for x, _ in values]
        ys = [y for _, y in values]
        return draw_int_grid(
            values,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"column_span (occupied world-z count)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys))
            + [column_diagnostics_summary(self._cols)],
            coord_prefix="tile-local ",
        )

    def render_cliff_delta(self) -> str:
        """Max |Δz_top| vs 4-neighbors — steep edge without mid-z cells = gap suspect."""
        if not self._cols:
            return ""
        values = values_cliff_delta(self._cols)
        if not values:
            return ""
        xs = [x for x, _ in values]
        ys = [y for _, y in values]
        return draw_int_grid(
            values,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"cliff_delta (max |Δz_top| to neighbors)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys))
            + [column_diagnostics_summary(self._cols)],
            coord_prefix="tile-local ",
        )

    def z_levels(self) -> list[int]:
        """Dense occupied world-z (every z in runs — mid-band of thick walls)."""
        return z_occupied(self._cols.values())

    def render_all_levels(
        self,
        *,
        include_z_slices: bool = True,
        include_column_diagnostics: bool = True,
    ) -> dict[str, str]:
        """Keys: surface; optional dense z slices; column_span / cliff_delta diagnostics."""
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        if include_column_diagnostics:
            span = self.render_column_span()
            if span:
                out[LEVEL_COLUMN_SPAN] = span
            cliff = self.render_cliff_delta()
            if cliff:
                out[LEVEL_CLIFF_DELTA] = cliff
        if not include_z_slices:
            return out
        for z, text in self.render_occupied_z_levels().items():
            out[str(z)] = text
        return out
