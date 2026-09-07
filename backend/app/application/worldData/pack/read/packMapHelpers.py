"""Shared helpers for pack map coordinate math."""

from __future__ import annotations

import math

from app.db.models.world import World


def world_map_cell_span(world: World) -> int:
    return world.fine_cells_per_map_cell


def tile_index(coord: int, tile_size: int) -> tuple[int, int]:
    gx = math.floor(coord / tile_size)
    local = coord - gx * tile_size
    return gx, local


def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
    """Macro-tile (gx, gy) containing fine-grid anchor."""
    tile_size = world_map_cell_span(world)
    gx, _ = tile_index(anchor_x, tile_size)
    gy, _ = tile_index(anchor_y, tile_size)
    return gx, gy


def world_map_sample_index(local: int, tile_size: int, cells_per_side: int) -> int:
    """Map fine-local offset inside a macro-tile to light ``tx``/``ty``.

    Used for pin placement and coarse sampling — **not** a substitute for the
    full L0 light mask (side×side wire cells).
    """
    if tile_size <= 0 or cells_per_side <= 0:
        return 0
    return min(cells_per_side - 1, max(0, local * cells_per_side // tile_size))
