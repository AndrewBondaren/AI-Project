"""Pack-native location terrain ASCII — ``l.{uid}.terrain.zst`` (FineTerrainChunkWire)."""

from __future__ import annotations

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    draw_grade_consume_grid,
    draw_int_grid,
    draw_symbol_grid,
    grade_consume_z_levels,
    paired_width_from_columns,
    symbols_at_z,
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
    grade_level_key,
)
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
        ray_index: GradeRayIndex | None = None,
    ) -> None:
        self._chunk = chunk
        self._volume = volume
        self.location_uid = location_uid
        self._cols: dict[tuple[int, int], FineTerrainColumnWire] = {
            (c.lx, c.ly): c for c in chunk.columns
        }
        self._rays = (ray_index or GradeRayIndex()).relative_to(volume.x0, volume.y0)

    def _col_bounds(self) -> tuple[int, int, int, int] | None:
        if not self._cols:
            return None
        xs = [x for x, _ in self._cols]
        ys = [y for _, y in self._cols]
        return min(xs), max(xs), min(ys), max(ys)

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
                f"location={self.location_uid}  "
                f"surface_z (column max world-z)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys)),
            coord_prefix="local ",
            width=paired_width_from_columns(self._cols),
        )

    def render_grade(self) -> str:
        """3×3 consume dump — omit when no leftover rays and no uid.

        Legend is not inlined (PAR-T-6); dump/HTTP use map+grade legends.
        """
        frame = self._col_bounds()
        if frame is None:
            return ""
        x0, x1, y0, y1 = frame
        return draw_grade_consume_grid(
            self._cols,
            self._rays,
            title=(
                f"location={self.location_uid}  "
                f"(pack location_terrain, surface_grade 3x3 rim rays)"
            ),
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="local ",
            bounds=frame,
        )

    def render_grade_at_z(self, z: int) -> str:
        """3×3 consume dump for cells whose surface_z == ``z``."""
        frame = self._col_bounds()
        if frame is None:
            return ""
        x0, x1, y0, y1 = frame
        return draw_grade_consume_grid(
            self._cols,
            self._rays,
            title=(
                f"location={self.location_uid} grade z={z}  "
                f"(pack location_terrain; 3x3, surface_z only)"
            ),
            extra_headers=self._extra_headers(x0, y0, x1, y1),
            coord_prefix="local ",
            bounds=frame,
            surface_z=int(z),
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
                f"location={self.location_uid} z={z}  "
                f"(pack location_terrain; cells present in FineTerrain only)"
            ),
        )

    def render_column_span(self) -> str:
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
                f"location={self.location_uid}  "
                f"column_span (occupied world-z count)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys))
            + [column_diagnostics_summary(self._cols)],
            coord_prefix="local ",
        )

    def render_cliff_delta(self) -> str:
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
                f"location={self.location_uid}  "
                f"cliff_delta (max |Δz_top| to neighbors)"
            ),
            extra_headers=self._extra_headers(min(xs), min(ys), max(xs), max(ys))
            + [column_diagnostics_summary(self._cols)],
            coord_prefix="local ",
        )

    def z_levels(self) -> list[int]:
        return z_occupied(self._cols.values())

    def render_all_levels(self, *, include_column_diagnostics: bool = True) -> dict[str, str]:
        """Keys: surface; surface_z; surface_grade; dense z; grade_{z}; optional column diagnostics."""
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
        for z in self.z_levels():
            text = self.render_level(z)
            if text.strip():
                out[str(z)] = text
        for z in grade_consume_z_levels(self._cols, self._rays):
            text = self.render_grade_at_z(int(z))
            if text.strip():
                out[grade_level_key(int(z))] = text
        return out
