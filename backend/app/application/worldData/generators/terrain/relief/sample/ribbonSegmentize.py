"""Split ribbon cells into contiguous terrain segments (RELIEF-T-32).

Pure: no pick / grade / world registry. Used by road_shoulder pick tests and
``grade_ribbon_segments`` (not occupancy sample).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.sample.terrainMap import map_system_terrain


@dataclass(frozen=True, slots=True)
class RibbonSegment:
    """One pick site: contiguous terrain run along a ribbon owner.

    ``owner_uid`` — connection edge uid (road). Omit when the front has no graph
    owner. Not a ``ReliefContext`` token.

    ``site_id`` — stable pick/seed key:
    ``{owner_uid}|{terrain_key}|{anchor_x},{anchor_y}`` where anchor = first
    cell of the run in walk order (not stamp geometry).
    """

    owner_uid: str | None
    terrain_key: str  # ReliefConditionTerrain value
    system_terrain: str
    dz: int
    site_id: str
    cell_coords: tuple[tuple[int, int], ...]  # (x,y) ribbon seed cells
    path_length: int | None = None


def segmentize_by_terrain(
    *,
    owner_uid: str,
    cells: Sequence[tuple[tuple[int, int], str, int] | tuple[tuple[int, int], str, int, int]],
) -> list[RibbonSegment]:
    """Split cells into segments on system_terrain change.

    ``cells``: ``((x, y), terrain, dz)`` or ``(..., path_length)`` in walk order.
    """
    segments: list[RibbonSegment] = []
    if not cells:
        return segments

    buf_coords: list[tuple[int, int]] = []
    cur_terrain = cells[0][1]
    cur_dz = cells[0][2]
    cur_path = cells[0][3] if len(cells[0]) > 3 else None
    for row in cells:
        xy, terrain, dz = row[0], row[1], row[2]
        path_length = row[3] if len(row) > 3 else None
        mapped = map_system_terrain(terrain)
        if mapped is None:
            if buf_coords:
                key = map_system_terrain(cur_terrain)
                if key is not None:
                    segments.append(
                        _seg(
                            owner_uid, key.value, cur_terrain, cur_dz,
                            buf_coords, cur_path,
                        )
                    )
                buf_coords = []
            cur_terrain = terrain
            cur_dz = dz
            cur_path = path_length
            continue
        if terrain != cur_terrain:
            key = map_system_terrain(cur_terrain)
            if key is not None and buf_coords:
                segments.append(
                    _seg(
                        owner_uid, key.value, cur_terrain, cur_dz,
                        buf_coords, cur_path,
                    )
                )
            buf_coords = [xy]
            cur_terrain = terrain
            cur_dz = dz
            cur_path = path_length
        else:
            buf_coords.append(xy)
            cur_dz = dz
            cur_path = path_length
    if buf_coords:
        key = map_system_terrain(cur_terrain)
        if key is not None:
            segments.append(
                _seg(
                    owner_uid, key.value, cur_terrain, cur_dz,
                    buf_coords, cur_path,
                )
            )
    return segments


def _seg(
    owner_uid: str,
    terrain_key: str,
    system_terrain: str,
    dz: int,
    coords: list[tuple[int, int]],
    path_length: int | None = None,
) -> RibbonSegment:
    site_id = f"{owner_uid}|{terrain_key}|{coords[0][0]},{coords[0][1]}"
    return RibbonSegment(
        owner_uid=owner_uid,
        terrain_key=terrain_key,
        system_terrain=system_terrain,
        dz=dz,
        site_id=site_id,
        cell_coords=tuple(coords),
        path_length=path_length,
    )
