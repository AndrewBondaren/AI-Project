"""Global world surface ASCII grid — debug / smoke (legacy MapCell path).

Not L0 pack mask SoT — pack worlds use ``WorldMapPackRenderer`` /
``PackMapGridRender`` light-grid mosaic instead.
"""

from __future__ import annotations

import json

from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.mapSymbols import (
    LOCATION_PIN_SYMBOL,
    render_map_legend,
    symbol_for_role_or_terrain,
)
from app.db.models.mapCell import MapCell


def _macro_top_surface_cells(
    cells: list[MapCell],
    cell_m: int,
) -> dict[tuple[int, int], MapCell]:
    """Aggregate fine meter cells → one top cell per macro tile (Gx, Gy)."""
    tops: dict[tuple[int, int], MapCell] = {}
    for cell in cells:
        if cell.system_building_element:
            continue
        gx = cell.x // cell_m
        gy = cell.y // cell_m
        key = (gx, gy)
        if key not in tops or cell.z > tops[key].z:
            tops[key] = cell
    return tops


def cell_symbol(cell: MapCell, *, mark_location: bool = False) -> str:
    if mark_location and cell.location_uid:
        return LOCATION_PIN_SYMBOL
    hydrology = cell.hydrology
    if isinstance(hydrology, str):
        try:
            hydrology = json.loads(hydrology)
        except json.JSONDecodeError:
            hydrology = None
    role: str | None = None
    if isinstance(hydrology, dict):
        raw = hydrology.get("role")
        if raw:
            role = str(raw)
    return symbol_for_role_or_terrain(
        hydrology_role=role,
        system_terrain=cell.system_terrain,
    )


class WorldGridRenderer:
    """Top-surface world map — macro tile grid (aggregated from fine cells)."""

    def __init__(
        self,
        cells: list[MapCell],
        *,
        cell_size_m: int | None = None,
    ) -> None:
        self._cell_m = cell_size_m or 1000
        self._tops = _macro_top_surface_cells(cells, self._cell_m)

    @staticmethod
    def render_legend(*, mark_location: bool = False) -> str:
        return render_map_legend(
            mark_location=mark_location,
            pin_label="map_cell.location_uid set",
        )

    def render_bbox(
        self,
        gx0: int,
        gy0: int,
        gx1: int,
        gy1: int,
        *,
        mark_location: bool = False,
    ) -> str:
        lines: list[str] = [
            format_grid_header(gx0, gx1, gy0, gy1, cell_size_m=self._cell_m),
        ]
        for gy in range(gy1, gy0 - 1, -1):
            row = "".join(
                cell_symbol(self._tops[(gx, gy)], mark_location=mark_location)
                if (gx, gy) in self._tops
                else " "
                for gx in range(gx0, gx1 + 1)
            )
            lines.append(f"{gy:4d} |{row}|")
        return "\n".join(lines)

    def render(self, *, mark_location: bool = False) -> str:
        if not self._tops:
            return ""
        xs = [x for x, _ in self._tops]
        ys = [y for _, y in self._tops]
        return self.render_bbox(min(xs), min(ys), max(xs), max(ys), mark_location=mark_location)
