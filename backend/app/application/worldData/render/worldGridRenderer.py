"""Global world surface ASCII grid — debug / smoke."""

from __future__ import annotations

import json

from app.application.worldData.render.gridAxes import format_grid_header
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation

_ROLE_SYMBOLS: dict[str, str] = {
    "coastal_sea": "~",
    "open_ocean": "≈",
    "lake": "o",
    "river_bed": "r",
    "shore": "s",
}

_TERRAIN_SYMBOLS: dict[str, str] = {
    "liquid_body": "~",
    "plains": ".",
    "forest": "f",
    "shore": "s",
    "urban": "u",
}

_LOCATION_BOUND_SYMBOL = "@"


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
        return _LOCATION_BOUND_SYMBOL
    hydrology = cell.hydrology
    if isinstance(hydrology, str):
        try:
            hydrology = json.loads(hydrology)
        except json.JSONDecodeError:
            hydrology = None
    if isinstance(hydrology, dict):
        role = hydrology.get("role")
        if role:
            return _ROLE_SYMBOLS.get(str(role), str(role)[0])
    terrain = cell.system_terrain
    if terrain:
        return _TERRAIN_SYMBOLS.get(str(terrain), str(terrain)[0])
    return "?"


class WorldGridRenderer:
    """Top-surface world map — macro tile grid (aggregated from fine cells)."""

    def __init__(
        self,
        cells: list[MapCell],
        locations: list[NamedLocation] | None = None,
        *,
        cell_size_m: int | None = None,
    ) -> None:
        self._cell_m = cell_size_m or 1000
        self._tops = _macro_top_surface_cells(cells, self._cell_m)
        self._locations = locations or []

    @staticmethod
    def render_legend(*, mark_location: bool = False) -> str:
        role_part = " ".join(f"{sym}={name}" for name, sym in _ROLE_SYMBOLS.items())
        terrain_part = " ".join(f"{sym}={name}" for name, sym in _TERRAIN_SYMBOLS.items())
        lines = [
            f"hydrology: {role_part}",
            f"terrain: {terrain_part}",
        ]
        if mark_location:
            lines.append(f"binding: {_LOCATION_BOUND_SYMBOL}=map_cell.location_uid set")
        lines.append("?=unknown")
        return "\n".join(lines)

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

    def build_bbox(self, gx0: int, gy0: int, gx1: int, gy1: int) -> str:
        return self.render_bbox(gx0, gy0, gx1, gy1)

    def build(self) -> str:
        return self.render()


WorldGridBuilder = WorldGridRenderer
