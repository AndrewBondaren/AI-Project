"""L0 world-grade ASCII — PAR-G5 omit (not dump SoT). Leftover until R36i-T-3a dump cleanup."""

from __future__ import annotations

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.fineTerrainAsciiKernel import draw_symbol_grid
from app.application.worldData.render.lightMapCells import wire_grade_symbol
from app.application.worldData.render.lightMosaicFrame import (
    MosaicFrame,
    TileIndex,
    cell_at_world,
    resolve_mosaic_frame,
)
from app.application.worldData.render.mapSymbols import GRADE_EMPTY_SYMBOL, render_grade_legend


def _grade_hits_tile(tile: PackTileLightView) -> dict[tuple[int, int], str]:
    hits: dict[tuple[int, int], str] = {}
    for (tx, ty), cell in tile.cells.items():
        sym = wire_grade_symbol(cell)
        if sym != GRADE_EMPTY_SYMBOL:
            hits[(tx, ty)] = sym
    return hits


def _grade_hits_mosaic(by_xy: TileIndex, frame: MosaicFrame) -> dict[tuple[int, int], str]:
    hits: dict[tuple[int, int], str] = {}
    for wy in range(frame.ly0, frame.ly1 + 1):
        for wx in range(frame.lx0, frame.lx1 + 1):
            cell = cell_at_world(by_xy, frame, wx, wy)
            if cell is None:
                continue
            sym = wire_grade_symbol(cell)
            if sym != GRADE_EMPTY_SYMBOL:
                hits[(wx, wy)] = sym
    return hits


def render_tile_light_grade_grid(
    by_xy: TileIndex,
    gx: int,
    gy: int,
    tile_size_m: int,
) -> str:
    tile = by_xy.get((gx, gy))
    if tile is None or tile.side <= 0:
        return ""
    hits = _grade_hits_tile(tile)
    if not hits:
        return ""
    ascii_g = draw_symbol_grid(
        hits,
        title=(
            f"tile Gx={gx} Gy={gy}  "
            f"(pack L0 grade grid crop "
            f"{min(x for x, _ in hits)}..{max(x for x, _ in hits)}"
            f"×{min(y for _, y in hits)}..{max(y for _, y in hits)})"
        ),
        coord_prefix="light ",
        cell_size_m=max(1, int(tile_size_m) // tile.side),
        x_rulers=True,
    )
    return f"{ascii_g}\n\n{render_grade_legend()}"


def render_light_grade_mosaic(
    by_xy: TileIndex,
    tile_size_m: int,
    *,
    gx0: int | None = None,
    gy0: int | None = None,
    gx1: int | None = None,
    gy1: int | None = None,
) -> tuple[str, str]:
    frame = resolve_mosaic_frame(
        by_xy, tile_size_m, gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1,
    )
    if frame is None:
        return "", ""
    hits = _grade_hits_mosaic(by_xy, frame)
    if not hits:
        return "", ""
    xs = [x for x, _ in hits]
    ys = [y for _, y in hits]
    ascii_g = draw_symbol_grid(
        hits,
        title=(
            f"pack L0 grade mosaic  "
            f"(crop light x{min(xs)}..{max(xs)} y{min(ys)}..{max(ys)}; "
            f"{len(hits)} grade cells; "
            f"macro Gx{frame.gx0}..Gx{frame.gx1} Gy{frame.gy0}..Gy{frame.gy1})"
        ),
        coord_prefix="light ",
        cell_size_m=frame.light_m,
        x_rulers=True,
    )
    return ascii_g, render_grade_legend()
