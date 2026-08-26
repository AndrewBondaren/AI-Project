"""Collect L0 light cells → dicts for ``draw_symbol_grid`` / ``draw_int_grid``."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.lightMapCells import wire_symbol
from app.application.worldData.render.lightMapPins import pin_light_xy_on_tile
from app.application.worldData.render.lightMosaicFrame import (
    MosaicFrame,
    TileIndex,
    cell_at_world,
)
from app.application.worldData.render.mapSymbols import LOCATION_PIN_SYMBOL
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin


def collect_mask_symbols(
    by_xy: TileIndex,
    frame: MosaicFrame,
    *,
    pin_wxy: set[tuple[int, int]],
    mark_location: bool,
) -> dict[tuple[int, int], str]:
    symbols: dict[tuple[int, int], str] = {}
    for wy in range(frame.ly0, frame.ly1 + 1):
        for wx in range(frame.lx0, frame.lx1 + 1):
            if mark_location and (wx, wy) in pin_wxy:
                symbols[(wx, wy)] = LOCATION_PIN_SYMBOL
                continue
            cell = cell_at_world(by_xy, frame, wx, wy)
            if cell is None:
                continue
            symbols[(wx, wy)] = wire_symbol(cell, mark_pin=mark_location)
    return symbols


def collect_height_values(
    by_xy: TileIndex,
    frame: MosaicFrame,
) -> dict[tuple[int, int], int]:
    values: dict[tuple[int, int], int] = {}
    for wy in range(frame.ly0, frame.ly1 + 1):
        for wx in range(frame.lx0, frame.lx1 + 1):
            cell = cell_at_world(by_xy, frame, wx, wy)
            if cell is not None:
                values[(wx, wy)] = int(cell.surface_z)
    return values


def collect_tile_mask_symbols(
    tile: PackTileLightView,
    pins: Iterable[LocationsIndexPin],
    tile_size_m: int,
    *,
    mark_location: bool,
) -> dict[tuple[int, int], str]:
    pin_xy = pin_light_xy_on_tile(pins, tile, tile_size_m) if mark_location else set()
    symbols: dict[tuple[int, int], str] = {}
    for ty in range(tile.side):
        for tx in range(tile.side):
            if mark_location and (tx, ty) in pin_xy:
                symbols[(tx, ty)] = LOCATION_PIN_SYMBOL
                continue
            cell = tile.cells.get((tx, ty))
            if cell is None:
                continue
            symbols[(tx, ty)] = wire_symbol(cell, mark_pin=mark_location)
    return symbols


def collect_tile_height_values(tile: PackTileLightView) -> dict[tuple[int, int], int]:
    return {
        (tx, ty): int(cell.surface_z) for (tx, ty), cell in tile.cells.items()
    }


def render_all_tiles(
    keys: Iterable[tuple[int, int]],
    render_one: Callable[[int, int], str],
) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for gx, gy in sorted(keys):
        text = render_one(gx, gy)
        if text:
            out[(gx, gy)] = text
    return out
