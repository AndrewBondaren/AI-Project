"""Global world surface ASCII grid — debug / smoke."""

from __future__ import annotations

import json

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
}


def _top_surface_cells(cells: list[MapCell]) -> dict[tuple[int, int], MapCell]:
    tops: dict[tuple[int, int], MapCell] = {}
    for cell in cells:
        key = (cell.x, cell.y)
        if key not in tops or cell.z > tops[key].z:
            tops[key] = cell
    return tops


def _cell_symbol(cell: MapCell) -> str:
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


class WorldGridBuilder:
    """Top-surface world map render."""

    def __init__(
        self,
        cells: list[MapCell],
        locations: list[NamedLocation] | None = None,
    ) -> None:
        self._tops = _top_surface_cells(cells)
        self._locations = locations or []

    def build_bbox(
        self,
        gx0: int,
        gy0: int,
        gx1: int,
        gy1: int,
    ) -> str:
        lines: list[str] = [f"x: {gx0}..{gx1}  y: {gy0}..{gy1}"]
        for gy in range(gy1, gy0 - 1, -1):
            row = "".join(
                _cell_symbol(self._tops[(gx, gy)])
                if (gx, gy) in self._tops
                else " "
                for gx in range(gx0, gx1 + 1)
            )
            lines.append(f"{gy:4d} |{row}|")
        return "\n".join(lines)

    def build(self) -> str:
        if not self._tops:
            return ""
        xs = [x for x, _ in self._tops]
        ys = [y for _, y in self._tops]
        return self.build_bbox(min(xs), min(ys), max(xs), max(ys))
