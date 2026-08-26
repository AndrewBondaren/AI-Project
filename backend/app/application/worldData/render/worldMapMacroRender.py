"""Coarse L0 overview: one glyph per macro-tile. Not mask SoT."""

from __future__ import annotations

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.fineTerrainAsciiKernel import draw_symbol_grid
from app.application.worldData.render.lightMapCells import wire_symbol
from app.application.worldData.render.lightMosaicFrame import TileIndex
from app.application.worldData.render.mapSymbols import LOCATION_PIN_SYMBOL
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole


def rep_cell(tile: PackTileLightView):
    """Overview aggregate only — NOT L0 mask SoT."""
    if not tile.cells:
        return None
    mid = max(0, tile.side // 2)
    if (mid, mid) in tile.cells:
        return tile.cells[(mid, mid)]
    for cell in tile.cells.values():
        if cell.hydrology_role != WorldMapHydrologyRole.NONE:
            return cell
    return next(iter(tile.cells.values()))


def render_macro_bbox(
    by_xy: TileIndex,
    tile_size_m: int,
    pin_macros: set[tuple[int, int]],
    gx0: int,
    gy0: int,
    gx1: int,
    gy1: int,
    *,
    mark_location: bool = False,
) -> str:
    symbols: dict[tuple[int, int], str] = {}
    for gy in range(gy0, gy1 + 1):
        for gx in range(gx0, gx1 + 1):
            if mark_location and (gx, gy) in pin_macros:
                symbols[(gx, gy)] = LOCATION_PIN_SYMBOL
                continue
            tile = by_xy.get((gx, gy))
            if tile is None:
                continue
            cell = rep_cell(tile)
            if cell is not None:
                symbols[(gx, gy)] = wire_symbol(cell)
    return draw_symbol_grid(
        symbols,
        title="pack L0 MACRO AGGREGATE (not mask SoT) — one symbol per macro-tile",
        bounds=(gx0, gx1, gy0, gy1),
        cell_size_m=tile_size_m,
        x_rulers=False,
    )


def render_macro(
    by_xy: TileIndex,
    tile_size_m: int,
    pin_macros: set[tuple[int, int]],
    *,
    mark_location: bool = False,
) -> str:
    if not by_xy:
        return ""
    xs = [gx for gx, _ in by_xy]
    ys = [gy for _, gy in by_xy]
    return render_macro_bbox(
        by_xy, tile_size_m, pin_macros,
        min(xs), min(ys), max(xs), max(ys),
        mark_location=mark_location,
    )
