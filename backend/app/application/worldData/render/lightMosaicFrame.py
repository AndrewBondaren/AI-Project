"""L0 light mosaic frame — macro bbox → light-cell axes. No glyphs."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire

TileIndex = dict[tuple[int, int], PackTileLightView]


@dataclass(frozen=True)
class MosaicFrame:
    gx0: int
    gy0: int
    gx1: int
    gy1: int
    side: int
    light_m: int
    lx0: int
    lx1: int
    ly0: int
    ly1: int

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.lx0, self.lx1, self.ly0, self.ly1)


def resolve_mosaic_frame(
    by_xy: TileIndex,
    tile_size_m: int,
    *,
    gx0: int | None,
    gy0: int | None,
    gx1: int | None,
    gy1: int | None,
) -> MosaicFrame | None:
    """Prefer caller bbox (MLB-12). Omit bbox → baked tile extent.

    Missing macro-tiles inside the frame render as spaces (unmapped).
    """
    if gx0 is None or gy0 is None or gx1 is None or gy1 is None:
        if not by_xy:
            return None
        xs = [gx for gx, _ in by_xy]
        ys = [gy for _, gy in by_xy]
        gx0, gx1 = min(xs), max(xs)
        gy0, gy1 = min(ys), max(ys)
    elif not by_xy:
        return None

    side = 0
    for gy in range(gy0, gy1 + 1):
        for gx in range(gx0, gx1 + 1):
            tile = by_xy.get((gx, gy))
            if tile is not None and tile.side > 0:
                side = tile.side
                break
        if side > 0:
            break
    if side <= 0:
        for tile in by_xy.values():
            if tile.side > 0:
                side = tile.side
                break
    if side <= 0:
        return None

    return MosaicFrame(
        gx0=gx0,
        gy0=gy0,
        gx1=gx1,
        gy1=gy1,
        side=side,
        light_m=max(1, int(tile_size_m) // side),
        lx0=gx0 * side,
        lx1=(gx1 + 1) * side - 1,
        ly0=gy0 * side,
        ly1=(gy1 + 1) * side - 1,
    )


def cell_at_world(
    by_xy: TileIndex,
    frame: MosaicFrame,
    wx: int,
    wy: int,
) -> WorldMapCellWire | None:
    gx, tx = divmod(wx, frame.side)
    gy, ty = divmod(wy, frame.side)
    tile = by_xy.get((gx, gy))
    if tile is None:
        return None
    return tile.cells.get((tx, ty))
