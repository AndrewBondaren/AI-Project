"""Pure fine ↔ light ↔ macro coordinate conversion — tz_map_light_bake § Координаты.

Canonical owner of light-grid coordinate operations (PC-11.6a owner map).
``pack/bake/lightGrid/coords`` temporarily re-exports the same symbols.
"""

from app.dataModel.spatial.grid.lightGridScale import LightGridScale


def fine_to_light(x_fine: int, y_fine: int, scale: LightGridScale) -> tuple[int, int]:
    return x_fine // scale.light_span, y_fine // scale.light_span


def light_to_macro_local(lx: int, ly: int, scale: LightGridScale) -> tuple[int, int, int, int]:
    side = scale.side
    return lx // side, ly // side, lx % side, ly % side


def light_cell_origin_fine(gx: int, gy: int, tx: int, ty: int, scale: LightGridScale) -> tuple[int, int]:
    return gx * scale.tile_macro + tx * scale.light_span, gy * scale.tile_macro + ty * scale.light_span


def light_cell_center_fine(gx: int, gy: int, tx: int, ty: int, scale: LightGridScale) -> tuple[int, int]:
    ox, oy = light_cell_origin_fine(gx, gy, tx, ty, scale)
    half = scale.light_span // 2
    return ox + half, oy + half


def fine_to_macro_local(
    x_fine: int,
    y_fine: int,
    scale: LightGridScale,
) -> tuple[int, int, int, int]:
    lx, ly = fine_to_light(x_fine, y_fine, scale)
    return light_to_macro_local(lx, ly, scale)
