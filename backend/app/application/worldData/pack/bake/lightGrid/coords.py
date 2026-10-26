"""Light-grid coordinate helpers — tz_map_light_bake § Координаты / WP-10 v2."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.worldPack.wire.worldMapCellsPerTile import light_span_for


@dataclass(frozen=True)
class LightGridScale:
    tile_macro: int
    side: int
    light_span: int

    @classmethod
    def from_tile(cls, tile_macro: int, side: int) -> LightGridScale:
        side = max(1, int(side))
        tile_macro = max(1, int(tile_macro))
        return cls(tile_macro=tile_macro, side=side, light_span=light_span_for(tile_macro, side))

    def rim_tx_ty(self, facing: Facing) -> tuple[tuple[int, int], ...]:
        """Local (tx, ty) along the tile rim facing outward ``facing``.

        Index 0 / ``side-1`` from ``CARDINAL_WALL_OUTWARD_DELTA``, not world AABB.
        """
        dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
        last = self.side - 1
        if dx != 0:
            tx = last if dx > 0 else 0
            return tuple((tx, ty) for ty in range(self.side))
        ty = last if dy > 0 else 0
        return tuple((tx, ty) for tx in range(self.side))


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
