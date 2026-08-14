"""Light-grid coordinate helpers — tz_map_light_bake § Координаты / WP-10 v2."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.worldPack.worldMapCellsPerTile import light_m_for


@dataclass(frozen=True)
class LightGridScale:
    tile_m: int
    side: int
    light_m: int

    @classmethod
    def from_tile(cls, tile_m: int, side: int) -> LightGridScale:
        side = max(1, int(side))
        tile_m = max(1, int(tile_m))
        return cls(tile_m=tile_m, side=side, light_m=light_m_for(tile_m, side))

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


def meters_to_light(xm: int, ym: int, scale: LightGridScale) -> tuple[int, int]:
    return xm // scale.light_m, ym // scale.light_m


def light_to_macro_local(lx: int, ly: int, scale: LightGridScale) -> tuple[int, int, int, int]:
    side = scale.side
    return lx // side, ly // side, lx % side, ly % side


def light_cell_origin_m(gx: int, gy: int, tx: int, ty: int, scale: LightGridScale) -> tuple[int, int]:
    return gx * scale.tile_m + tx * scale.light_m, gy * scale.tile_m + ty * scale.light_m


def light_cell_center_m(gx: int, gy: int, tx: int, ty: int, scale: LightGridScale) -> tuple[int, int]:
    ox, oy = light_cell_origin_m(gx, gy, tx, ty, scale)
    half = scale.light_m // 2
    return ox + half, oy + half


def meters_to_macro_local(
    xm: int,
    ym: int,
    scale: LightGridScale,
) -> tuple[int, int, int, int]:
    lx, ly = meters_to_light(xm, ym, scale)
    return light_to_macro_local(lx, ly, scale)
