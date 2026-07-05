"""Per-location map_cells ASCII grid — debug / smoke."""

from __future__ import annotations

from app.application.worldData.generators.structure.gridRenderer import render_all_levels, render_level
from app.application.worldData.render.worldGridBuilder import _cell_symbol
from app.db.models.mapCell import MapCell


class LocationGridBuilder:
    """Render cells bound to one ``location_uid``."""

    def __init__(self, cells: list[MapCell], location_uid: str) -> None:
        self._cells = [c for c in cells if c.location_uid == location_uid]
        self.location_uid = location_uid

    def build_level(self, z: int) -> str:
        if not self._cells:
            return ""
        if any(c.system_building_element for c in self._cells if c.z == z):
            return render_level(self._cells, z)
        level = {(c.x, c.y): c for c in self._cells if c.z == z}
        if not level:
            return ""
        xs = [x for x, _ in level]
        ys = [y for _, y in level]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        lines: list[str] = [f"location={self.location_uid} z={z}"]
        for y in range(y1, y0 - 1, -1):
            row = "".join(
                _cell_symbol(level[(x, y)]) if (x, y) in level else " "
                for x in range(x0, x1 + 1)
            )
            lines.append(f"{y:4d} |{row}|")
        return "\n".join(lines)

    def build_all_levels(self) -> dict[int, str]:
        indoor = any(c.system_building_element for c in self._cells)
        if indoor:
            return render_all_levels(self._cells)
        return {
            z: self.build_level(z)
            for z in sorted({c.z for c in self._cells})
        }
