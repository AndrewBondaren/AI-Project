"""Split ribbon sample cells into contiguous terrain segments (RELIEF-T-32).

Pure: no pick / grade / world registry. Used by road_shoulder / open_land / shore.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.terrainMap import map_system_terrain


@dataclass(frozen=True, slots=True)
class RoadShoulderSegment:
    """One pick site: contiguous corridor terrain × side along an owner."""

    edge_uid: str
    terrain_key: str  # ReliefConditionTerrain value
    system_terrain: str
    dz: int
    site_id: str
    cell_coords: tuple[tuple[int, int], ...]  # (x,y) shoulder cells


def segmentize_by_terrain(
    *,
    edge_uid: str,
    cells: list[tuple[tuple[int, int], str, int]],
) -> list[RoadShoulderSegment]:
    """Split shoulder cells into segments on system_terrain change.

    cells: ((x,y), system_terrain, dz) in stable walk order along the edge side.
    """
    segments: list[RoadShoulderSegment] = []
    if not cells:
        return segments

    buf_coords: list[tuple[int, int]] = []
    cur_terrain = cells[0][1]
    cur_dz = cells[0][2]
    for (xy, terrain, dz) in cells:
        mapped = map_system_terrain(terrain)
        if mapped is None:
            if buf_coords:
                key = map_system_terrain(cur_terrain)
                if key is not None:
                    segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
                buf_coords = []
            cur_terrain = terrain
            cur_dz = dz
            continue
        if terrain != cur_terrain:
            key = map_system_terrain(cur_terrain)
            if key is not None and buf_coords:
                segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
            buf_coords = [xy]
            cur_terrain = terrain
            cur_dz = dz
        else:
            buf_coords.append(xy)
            cur_dz = dz
    if buf_coords:
        key = map_system_terrain(cur_terrain)
        if key is not None:
            segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
    return segments


def _seg(
    edge_uid: str,
    terrain_key: str,
    system_terrain: str,
    dz: int,
    coords: list[tuple[int, int]],
) -> RoadShoulderSegment:
    site_id = f"{edge_uid}|{terrain_key}|{coords[0][0]},{coords[0][1]}"
    return RoadShoulderSegment(
        edge_uid=edge_uid,
        terrain_key=terrain_key,
        system_terrain=system_terrain,
        dz=dz,
        site_id=site_id,
        cell_coords=tuple(coords),
    )
