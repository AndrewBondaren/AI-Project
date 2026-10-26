"""Light-grid scale contract — tz_map_light_bake § Координаты / WP-10 v2.

Canonical owner of ``LightGridScale`` and ``light_span_for`` (PC-11.6a owner
map). ``worldMapCellsPerTile`` and ``pack/bake/lightGrid/coords`` temporarily
re-export the same symbols; the aliases resolve in PC-11.6b.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing


def light_span_for(tile_macro: int, side: int) -> int:
    """Fine cells per light cell: ``fine_cells_per_map_cell // side`` (WP-10).

    Single SoT for ``LightGridScale.light_span`` and ``ParentLightTile.light_span``.
    """
    return max(1, int(tile_macro) // max(1, int(side)))


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
