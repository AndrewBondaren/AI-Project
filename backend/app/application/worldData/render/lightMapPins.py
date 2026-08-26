"""locations_index → L0 light / macro coordinates. Not ASCII."""

from __future__ import annotations

from collections.abc import Iterable

from app.application.worldData.pack.read.packMapHelpers import (
    tile_index,
    world_map_sample_index,
)
from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.lightMosaicFrame import MosaicFrame
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin


def pin_macro(pin: LocationsIndexPin, tile_size_m: int) -> tuple[int, int]:
    gx, _ = tile_index(pin.map_x, tile_size_m)
    gy, _ = tile_index(pin.map_y, tile_size_m)
    return gx, gy


def pin_macros(
    pins: Iterable[LocationsIndexPin],
    tile_size_m: int,
) -> set[tuple[int, int]]:
    return {pin_macro(pin, tile_size_m) for pin in pins}


def pin_light_xy(
    pin: LocationsIndexPin,
    tile: PackTileLightView,
    tile_size_m: int,
) -> tuple[int, int] | None:
    gx, lx = tile_index(pin.map_x, tile_size_m)
    gy, ly = tile_index(pin.map_y, tile_size_m)
    if gx != tile.gx or gy != tile.gy or tile.side <= 0:
        return None
    return (
        world_map_sample_index(lx, tile_size_m, tile.side),
        world_map_sample_index(ly, tile_size_m, tile.side),
    )


def pin_light_xy_on_tile(
    pins: Iterable[LocationsIndexPin],
    tile: PackTileLightView,
    tile_size_m: int,
) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for pin in pins:
        xy = pin_light_xy(pin, tile, tile_size_m)
        if xy is not None:
            out.add(xy)
    return out


def pin_world_xy(
    pins: Iterable[LocationsIndexPin],
    frame: MosaicFrame,
    tile_size_m: int,
) -> set[tuple[int, int]]:
    pin_wxy: set[tuple[int, int]] = set()
    for pin in pins:
        pgx, lx = tile_index(pin.map_x, tile_size_m)
        pgy, ly = tile_index(pin.map_y, tile_size_m)
        if not (frame.gx0 <= pgx <= frame.gx1 and frame.gy0 <= pgy <= frame.gy1):
            continue
        tx = world_map_sample_index(lx, tile_size_m, frame.side)
        ty = world_map_sample_index(ly, tile_size_m, frame.side)
        pin_wxy.add((pgx * frame.side + tx, pgy * frame.side + ty))
    return pin_wxy
