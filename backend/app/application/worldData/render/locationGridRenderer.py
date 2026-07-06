"""Per-location map_cells ASCII grid — debug / smoke."""

from __future__ import annotations

from app.application.worldData.generators.structure.gridRenderer import render_all_levels, render_level
from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.worldGridRenderer import WorldGridRenderer, cell_symbol
from app.db.models.mapCell import MapCell


class LocationGridRenderer:
    """Render cells bound to one ``location_uid``."""

    _STRUCTURE_LEGEND = (
        "structure: #=wall .=floor D=door O=window _=stair_floor "
        "↑↓→←=stairs T=trapdoor H=ladder"
    )

    def __init__(
        self,
        cells: list[MapCell],
        location_uid: str,
        *,
        cell_size_m: int | None = None,
    ) -> None:
        self._cells = [c for c in cells if c.location_uid == location_uid]
        self.location_uid = location_uid
        self._cell_size_m = cell_size_m

    def _indoor_cells(self) -> list[MapCell]:
        return [c for c in self._cells if c.system_building_element]

    def _outdoor_surface_cells(self) -> list[MapCell]:
        return [c for c in self._cells if not c.system_building_element]

    @staticmethod
    def render_legend(*, indoor: bool = False) -> str:
        if indoor:
            return LocationGridRenderer._STRUCTURE_LEGEND
        return WorldGridRenderer.render_legend()

    def render_level(self, z: int) -> str:
        indoor = self._indoor_cells()
        if indoor:
            return render_level(indoor, z)
        surface = self._outdoor_surface_cells()
        level = {(c.x, c.y): c for c in surface if c.z == z}
        if not level:
            return ""
        xs = [x for x, _ in level]
        ys = [y for _, y in level]
        gx0, gx1 = min(xs), max(xs)
        gy0, gy1 = min(ys), max(ys)
        lines: list[str] = [
            f"location={self.location_uid} z={z}",
            format_grid_header(gx0, gx1, gy0, gy1, cell_size_m=self._cell_size_m),
        ]
        for gy in range(gy1, gy0 - 1, -1):
            row = "".join(
                cell_symbol(level[(gx, gy)]) if (gx, gy) in level else " "
                for gx in range(gx0, gx1 + 1)
            )
            lines.append(f"{gy:4d} |{row}|")
        return "\n".join(lines)

    def render_all_levels(self) -> dict[int, str]:
        indoor = self._indoor_cells()
        if indoor:
            return render_all_levels(indoor)
        return {
            z: self.render_level(z)
            for z in sorted({c.z for c in self._outdoor_surface_cells()})
        }

    # Back-compat aliases
    def build_level(self, z: int) -> str:
        return self.render_level(z)

    def build_all_levels(self) -> dict[int, str]:
        return self.render_all_levels()


LocationGridBuilder = LocationGridRenderer
