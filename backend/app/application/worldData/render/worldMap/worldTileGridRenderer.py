"""Per macro-tile local fine grid — fine_cells_per_map_cell × fine_cells_per_map_cell."""

from __future__ import annotations

from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.worldGridRenderer import cell_symbol
from app.db.models.mapCell import MapCell


class WorldTileGridRenderer:
    """Render one world macro tile at fine meter resolution."""

    def __init__(
        self,
        cells: list[MapCell],
        *,
        tile_gx: int,
        tile_gy: int,
        fine_span: int,
    ) -> None:
        self._cell_m = fine_span
        self._tile_gx = tile_gx
        self._tile_gy = tile_gy
        self._x0 = tile_gx * fine_span
        self._y0 = tile_gy * fine_span
        self._cells = [
            c for c in cells
            if not c.system_building_element
            and self._x0 <= c.x < self._x0 + fine_span
            and self._y0 <= c.y < self._y0 + fine_span
        ]

    @staticmethod
    def render_legend() -> str:
        from app.application.worldData.render.worldGridRenderer import WorldGridRenderer
        return WorldGridRenderer.render_legend()

    def _local_xy(self, cell: MapCell) -> tuple[int, int]:
        return cell.x - self._x0, cell.y - self._y0

    def render_surface_top(self) -> str:
        tops: dict[tuple[int, int], MapCell] = {}
        for cell in self._cells:
            lx, ly = self._local_xy(cell)
            key = (lx, ly)
            if key not in tops or cell.z > tops[key].z:
                tops[key] = cell
        if not tops:
            return ""
        lines = [
            f"tile Gx={self._tile_gx} Gy={self._tile_gy}  (local fine grid, top z)",
            format_grid_header(
                0, self._cell_m - 1,
                0, self._cell_m - 1,
                fine_span=1,
                prefix="local ",
            ),
        ]
        for ly in range(self._cell_m - 1, -1, -1):
            row = "".join(
                cell_symbol(tops[(lx, ly)]) if (lx, ly) in tops else " "
                for lx in range(self._cell_m)
            )
            lines.append(f"{ly:4d} |{row}|")
        return "\n".join(lines)

    def render_level(self, z: int) -> str:
        level = {}
        for cell in self._cells:
            if cell.z != z:
                continue
            level[self._local_xy(cell)] = cell
        if not level:
            return ""
        lines = [
            f"tile Gx={self._tile_gx} Gy={self._tile_gy} z={z}",
            format_grid_header(
                0, self._cell_m - 1,
                0, self._cell_m - 1,
                fine_span=1,
                prefix="local ",
            ),
        ]
        for ly in range(self._cell_m - 1, -1, -1):
            row = "".join(
                cell_symbol(level[(lx, ly)]) if (lx, ly) in level else " "
                for lx in range(self._cell_m)
            )
            lines.append(f"{ly:4d} |{row}|")
        return "\n".join(lines)

    def render_all_levels(self) -> dict[int, str]:
        z_levels = sorted({c.z for c in self._cells})
        out: dict[int, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[-1] = surface
        for z in z_levels:
            level = self.render_level(z)
            if level:
                out[z] = level
        return out
