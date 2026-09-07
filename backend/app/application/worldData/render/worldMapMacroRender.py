"""Coarse L0 overview: one glyph per macro-tile. Not mask SoT."""

from __future__ import annotations

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.fineTerrainAsciiKernel import draw_symbol_grid
from app.application.worldData.render.lightMapCells import wire_symbol
from app.application.worldData.render.lightMosaicFrame import TileIndex
from app.application.worldData.render.locationPinOverlay import l0_settlement_glyph, pin_at
from app.application.worldData.render.mapSymbols import LOCATION_PIN_SYMBOL
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin


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


def tile_has_settlement_footprint(tile: PackTileLightView) -> bool:
    return any(cell.location_pin is not None for cell in tile.cells.values())


def tile_settlement_glyph(
    tile: PackTileLightView,
    pins: list[LocationsIndexPin] | None,
    location_types: WorldLocationTypeRegistry | None,
) -> str | None:
    for cell in tile.cells.values():
        if cell.location_pin is None:
            continue
        return l0_settlement_glyph(
            pin_at(pins, cell.location_pin),
            location_types=location_types,
        )
    return None


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
    index_pins: list[LocationsIndexPin] | None = None,
    location_types: WorldLocationTypeRegistry | None = None,
) -> str:
    symbols: dict[tuple[int, int], str] = {}
    for gy in range(gy0, gy1 + 1):
        for gx in range(gx0, gx1 + 1):
            tile = by_xy.get((gx, gy))
            if tile is not None and tile_has_settlement_footprint(tile):
                glyph = tile_settlement_glyph(tile, index_pins, location_types)
                if glyph is not None:
                    symbols[(gx, gy)] = glyph
                    continue
            if mark_location and (gx, gy) in pin_macros:
                symbols[(gx, gy)] = LOCATION_PIN_SYMBOL
                continue
            if tile is None:
                continue
            cell = rep_cell(tile)
            if cell is not None:
                symbols[(gx, gy)] = wire_symbol(
                    cell, pins=index_pins, location_types=location_types,
                )
    return draw_symbol_grid(
        symbols,
        title="pack L0 MACRO AGGREGATE (not mask SoT) — one symbol per macro-tile",
        bounds=(gx0, gx1, gy0, gy1),
        fine_span=tile_size_m,
        x_rulers=False,
    )


def render_macro(
    by_xy: TileIndex,
    tile_size_m: int,
    pin_macros: set[tuple[int, int]],
    *,
    mark_location: bool = False,
    index_pins: list[LocationsIndexPin] | None = None,
    location_types: WorldLocationTypeRegistry | None = None,
) -> str:
    if not by_xy:
        return ""
    xs = [gx for gx, _ in by_xy]
    ys = [gy for _, gy in by_xy]
    return render_macro_bbox(
        by_xy, tile_size_m, pin_macros,
        min(xs), min(ys), max(xs), max(ys),
        mark_location=mark_location,
        index_pins=index_pins,
        location_types=location_types,
    )
