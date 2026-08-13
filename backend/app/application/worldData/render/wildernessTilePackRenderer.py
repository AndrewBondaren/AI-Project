"""Pack-native wilderness L2 ASCII — mosaic of ``r.{gx}.{gy}.c.{cx}.{cy}.zst`` chunks."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    draw_int_grid,
    draw_symbol_grid,
    symbols_at_z,
    symbols_at_z_with_grade,
    symbols_by_occupied_z,
    symbols_grade_by_surface_z,
    symbols_surface_top,
    symbols_surface_with_grade,
    values_cliff_delta,
    values_column_span,
    z_occupied,
)
from app.application.worldData.render.mapSymbols import render_map_legend
from app.application.worldData.render.renderPayloads import (
    LEVEL_CLIFF_DELTA,
    LEVEL_COLUMN_SPAN,
    LEVEL_SURFACE,
    LEVEL_SURFACE_GRADE,
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

    def mosaic_xy_bounds(self) -> tuple[int, int, int, int] | None:
        """Inclusive tile-local (x0,x1,y0,y1) over all mosaic columns — max frame for z-slices."""
        if not self._cols:
            return None
        xs = [x for x, _ in self._cols]
        ys = [y for _, y in self._cols]
        return min(xs), max(xs), min(ys), max(ys)

    def _draw(
        self,
        symbols: dict[tuple[int, int], str],
        *,
        title: str,
        bounds: tuple[int, int, int, int] | None = None,
    ) -> str:
        """ASCII grid; ``bounds`` locks frame (empty cells → space)."""
        frame = bounds
        if frame is None and symbols:
            xs = [x for x, _ in symbols]
            ys = [y for _, y in symbols]
            frame = (min(xs), max(xs), min(ys), max(ys))
        if frame is None:
            return ""
        x0, x1, y0, y1 = frame
        return draw_symbol_grid(
            symbols,
            title=title,
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="tile-local ",
            bounds=frame,
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
            bounds=self.mosaic_xy_bounds(),
        )

    def render_grade(self) -> str:
        """Surface + grade composite — omit when no ``system_grade_uid`` (PAR-G4)."""
        symbols = symbols_surface_with_grade(self._cols)
        if not symbols:
            return ""
        return self._draw(
            symbols,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"(pack wilderness_chunk mosaic, surface_grade = surface+grade)"
            ),
            bounds=self.mosaic_xy_bounds(),
        )

    def render_grade_at_z(
        self,
        z: int,
        *,
        by_surface_z: Mapping[int, Mapping[tuple[int, int], str]] | None = None,
    ) -> str:
        """Material at ``z`` + grade where surface_z == ``z``; mosaic frame; omit if no grade."""
        symbols = symbols_at_z_with_grade(
            self._cols, z, by_surface_z=by_surface_z,
        )
        if not symbols:
            return ""
        return self._draw(
            symbols,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy}) grade z={z}  "
                f"(pack wilderness_chunk mosaic; material+grade, surface_z only)"
            ),
            bounds=self.mosaic_xy_bounds(),
        )

    def iter_grade_z_levels_aligned(self):
        """Yield ``(z, ascii)`` grade overlays on mosaic frame (non-empty only)."""
        by_z = symbols_grade_by_surface_z(self._cols)
        for z in sorted(by_z):
            text = self.render_grade_at_z(int(z), by_surface_z=by_z)
            if text.strip():
                yield int(z), text

    def render_level(self, z: int) -> str:
        """Horizontal slice at world-z — mosaic frame; missing cells are spaces."""
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
            bounds=self.mosaic_xy_bounds(),
        )

    def render_occupied_z_levels(self) -> dict[int, str]:
        """ASCII per occupied world-z on the shared mosaic frame (aligned axes)."""
        if not self._cols:
            return {}
        frame = self.mosaic_xy_bounds()
        by_z = symbols_by_occupied_z(self._cols)
        out: dict[int, str] = {}
        for z in sorted(by_z):
            text = self._draw(
                by_z[z],
                title=(
                    f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                    f"(pack wilderness_chunk mosaic; cells present in FineTerrain only)"
                ),
                bounds=frame,
            )
            if text.strip():
                out[int(z)] = text
        return out

    def iter_occupied_z_levels_aligned(self):
        """Yield ``(z, ascii)`` on mosaic frame; frees per-z symbol maps as it goes."""
        frame = self.mosaic_xy_bounds()
        if frame is None:
            return
        by_z = symbols_by_occupied_z(self._cols)
        for z in sorted(by_z):
            cells = by_z.pop(z)
            text = self._draw(
                cells,
                title=(
                    f"wilderness tile=({self.tile_gx},{self.tile_gy}) z={z}  "
                    f"(pack wilderness_chunk mosaic; cells present in FineTerrain only)"
                ),
                bounds=frame,
            )
            if text.strip():
                yield int(z), text

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
        """Keys: surface; surface_grade; optional dense z; column diagnostics.

        Per-z grade files are dump-only (``z/grade_{n}.txt``) to avoid mega JSON —
        use ``iter_grade_z_levels_aligned`` / ``render_grade_at_z``.
        """
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        grade = self.render_grade()
        if grade:
            out[LEVEL_SURFACE_GRADE] = grade
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
