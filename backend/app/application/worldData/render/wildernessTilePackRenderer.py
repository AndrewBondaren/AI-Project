"""Pack-native wilderness L2 ASCII — mosaic of ``r.{gx}.{gy}.c.{cx}.{cy}.zst`` chunks."""

from __future__ import annotations

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    draw_grade_consume_grid,
    draw_int_grid,
    draw_symbol_grid,
    grade_consume_z_levels,
    paired_width_from_columns,
    symbols_at_z,
    symbols_by_occupied_z,
    symbols_surface_top,
    values_cliff_delta,
    values_column_span,
    values_surface_z,
    z_occupied,
)
from app.application.worldData.render.gradeRayDump import GradeRayIndex
from app.application.worldData.render.mapSymbols import render_map_legend
from app.application.worldData.render.renderPayloads import (
    LEVEL_CLIFF_DELTA,
    LEVEL_COLUMN_SPAN,
    LEVEL_SURFACE,
    LEVEL_SURFACE_GRADE,
    LEVEL_SURFACE_Z,
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
        ray_index: GradeRayIndex | None = None,
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
        origin_x = int(tile_gx) * int(tile_size_m)
        origin_y = int(tile_gy) * int(tile_size_m)
        self._rays = (ray_index or GradeRayIndex()).relative_to(origin_x, origin_y)

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

    def render_surface_z(self) -> str:
        """Per-cell max world-z (FineTerrain top) — L2 analog of L0 ``height``."""
        if not self._cols:
            return ""
        values = values_surface_z(self._cols)
        if not values:
            return ""
        xs = [x for x, _ in values]
        ys = [y for _, y in values]
        return draw_int_grid(
            values,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"surface_z (column max world-z)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys)),
            coord_prefix="tile-local ",
            width=paired_width_from_columns(self._cols),
        )

    def render_grade(self) -> str:
        """3×3 consume dump — omit when no leftover rays and no uid."""
        if not self._cols:
            return ""
        frame = self.mosaic_xy_bounds()
        if frame is None:
            return ""
        x0, x1, y0, y1 = frame
        return draw_grade_consume_grid(
            self._cols,
            self._rays,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy})  "
                f"(pack wilderness_chunk mosaic, surface_grade 3x3 rim rays)"
            ),
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="tile-local ",
            bounds=frame,
        )

    def render_grade_at_z(self, z: int) -> str:
        """3×3 consume dump for cells whose surface_z == ``z``; mosaic frame."""
        if not self._cols:
            return ""
        frame = self.mosaic_xy_bounds()
        if frame is None:
            return ""
        x0, x1, y0, y1 = frame
        return draw_grade_consume_grid(
            self._cols,
            self._rays,
            title=(
                f"wilderness tile=({self.tile_gx},{self.tile_gy}) grade z={z}  "
                f"(pack wilderness_chunk mosaic; 3x3, surface_z only)"
            ),
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="tile-local ",
            bounds=frame,
            surface_z=int(z),
        )

    def iter_grade_z_levels_aligned(self):
        """Yield ``(z, ascii)`` grade consume dumps on mosaic frame."""
        for z in grade_consume_z_levels(self._cols, self._rays):
            text = self.render_grade_at_z(int(z))
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
        """Keys: surface; surface_z; surface_grade; optional dense z; column diagnostics.

        Per-z grade files are dump-only (``z/grade_{n}.txt``) to avoid mega JSON —
        use ``iter_grade_z_levels_aligned`` / ``render_grade_at_z``.
        """
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        height = self.render_surface_z()
        if height:
            out[LEVEL_SURFACE_Z] = height
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
