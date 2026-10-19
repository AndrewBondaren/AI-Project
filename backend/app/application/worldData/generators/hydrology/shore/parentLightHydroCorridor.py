"""Hard hydro corridor from L0 parent light (WP-PERF-22)."""

from __future__ import annotations

from app.application.worldData.generators.coordinates.worldTile import world_fine_xy
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile


def hydro_mask_from_parent(
    parent: ParentLightTile,
) -> dict[tuple[int, int], MapCellHydrology]:
    """Expand L0 hydrology_role (+ width) to fine cells via ``to_fine_role``."""
    out: dict[tuple[int, int], MapCellHydrology] = {}
    tile_macro = parent.tile_macro
    side = parent.side
    light_span = parent.light_span

    for ty in range(side):
        for tx in range(side):
            cell = parent.cell_at(tx, ty)
            if cell is None:
                continue
            role = cell.hydrology_role
            if role is WorldMapHydrologyRole.NONE:
                continue
            fine = role.to_fine_role()
            if fine is None:
                continue
            entry = MapCellHydrology(role=fine)
            # Paint fine cells covered by this light cell.
            for dty in range(light_span):
                for dtx in range(light_span):
                    lx = tx * light_span + dtx
                    ly = ty * light_span + dty
                    if lx >= tile_macro or ly >= tile_macro:
                        continue
                    xm, ym = world_fine_xy(parent.gx, parent.gy, lx, ly, tile_macro)
                    out[(xm, ym)] = entry

            # Dilate river width in fine cells (hydrology_width on wire).
            if role is WorldMapHydrologyRole.RIVER and cell.hydrology_width:
                radius = max(0, int(cell.hydrology_width) - 1)
                if radius <= 0:
                    continue
                cx = parent.gx * tile_macro + tx * light_span + light_span // 2
                cy = parent.gy * tile_macro + ty * light_span + light_span // 2
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if abs(dx) + abs(dy) > radius:
                            continue
                        xm, ym = cx + dx, cy + dy
                        # Stay inside macro tile.
                        if not (
                            parent.gx * tile_macro <= xm < (parent.gx + 1) * tile_macro
                            and parent.gy * tile_macro <= ym < (parent.gy + 1) * tile_macro
                        ):
                            continue
                        prev = out.get((xm, ym))
                        if prev is None or prev.role is None:
                            out[(xm, ym)] = entry

    return out


def merge_hydro_hard_corridor(
    parent: ParentLightTile,
    sparse_fine_hydro: dict[tuple[int, int], MapCellHydrology] | None,
) -> dict[tuple[int, int], MapCellHydrology]:
    """L0 mask is SoT; sparse declared carves kept only inside corridor."""
    mask = hydro_mask_from_parent(parent)
    if not sparse_fine_hydro:
        return mask
    for key, entry in sparse_fine_hydro.items():
        if key in mask:
            mask[key] = entry
    return mask
