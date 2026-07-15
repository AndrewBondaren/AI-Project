"""Hard hydro corridor from L0 parent light (WP-PERF-22)."""

from __future__ import annotations

from app.application.worldData.generators.coordinates.worldTile import world_meter_xy
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.parentLightTile import ParentLightTile


def hydro_mask_from_parent(
    parent: ParentLightTile,
) -> dict[tuple[int, int], MapCellHydrology]:
    """Expand L0 hydrology_role (+ width) to meter cells via ``to_fine_role``."""
    out: dict[tuple[int, int], MapCellHydrology] = {}
    tile_m = parent.tile_m
    side = parent.side
    light_m = parent.light_m

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
            # Paint meters covered by this light cell.
            for dty in range(light_m):
                for dtx in range(light_m):
                    lx = tx * light_m + dtx
                    ly = ty * light_m + dty
                    if lx >= tile_m or ly >= tile_m:
                        continue
                    xm, ym = world_meter_xy(parent.gx, parent.gy, lx, ly, tile_m)
                    out[(xm, ym)] = entry

            # Dilate river width in meters (hydrology_width on wire).
            if role is WorldMapHydrologyRole.RIVER and cell.hydrology_width:
                radius = max(0, int(cell.hydrology_width) - 1)
                if radius <= 0:
                    continue
                cx = parent.gx * tile_m + tx * light_m + light_m // 2
                cy = parent.gy * tile_m + ty * light_m + light_m // 2
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if abs(dx) + abs(dy) > radius:
                            continue
                        xm, ym = cx + dx, cy + dy
                        # Stay inside macro tile.
                        if not (
                            parent.gx * tile_m <= xm < (parent.gx + 1) * tile_m
                            and parent.gy * tile_m <= ym < (parent.gy + 1) * tile_m
                        ):
                            continue
                        prev = out.get((xm, ym))
                        if prev is None or prev.role is None:
                            out[(xm, ym)] = entry

    return out


def merge_hydro_hard_corridor(
    parent: ParentLightTile,
    sparse_meter_hydro: dict[tuple[int, int], MapCellHydrology] | None,
) -> dict[tuple[int, int], MapCellHydrology]:
    """L0 mask is SoT; sparse declared carves kept only inside corridor."""
    mask = hydro_mask_from_parent(parent)
    if not sparse_meter_hydro:
        return mask
    for key, entry in sparse_meter_hydro.items():
        if key in mask:
            mask[key] = entry
    return mask
