"""Hill consumers — plains and forest independently.

Helper is ``hillRaster.raster_hill``. This module places origins
(``min_spacing``) and applies ``Δz``. Does not load world JSON.
SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
"""

from __future__ import annotations

from collections.abc import Mapping, Set

from app.application.worldData.generators.terrain.hills.hillRaster import (
    Coord,
    raster_hill,
)
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.terrainMasks.hillPolicy import HillPolicy


def place_hills(
    surface_z: dict[Coord, int],
    surface_terrain: Mapping[Coord, str],
    l0_hydro: Mapping[Coord, MapCellHydrology] | Set[Coord],
    *,
    plains_key: str,
    forest_key: str,
    plains_hills: HillPolicy,
    forest_hills: HillPolicy,
    seed: int,
    z_min: int,
    z_max: int,
) -> None:
    """Mutate ``surface_z`` in place. ``system_terrain`` is not written.

    Host = current L2 meters with that consumer's nearest-carry terrain
    and no L0 hydro role. Skip the whole hill if the footprint does not fit.
    ``z_band`` is not applied here.
    """
    if not surface_z:
        return
    hydro_xy: Set[Coord]
    if isinstance(l0_hydro, (set, frozenset)):
        hydro_xy = l0_hydro
    else:
        hydro_xy = set(l0_hydro.keys())
    base_z = dict(surface_z)
    _place_consumer(
        surface_z,
        base_z,
        _host_for(surface_z, surface_terrain, hydro_xy, plains_key),
        plains_hills,
        seed=seed,
        salt=_salt(plains_key),
        z_min=z_min,
        z_max=z_max,
    )
    _place_consumer(
        surface_z,
        base_z,
        _host_for(surface_z, surface_terrain, hydro_xy, forest_key),
        forest_hills,
        seed=seed,
        salt=_salt(forest_key),
        z_min=z_min,
        z_max=z_max,
    )


def _host_for(
    surface_z: Mapping[Coord, int],
    surface_terrain: Mapping[Coord, str],
    hydro_xy: Set[Coord],
    terrain_key: str,
) -> set[Coord]:
    return {
        xy
        for xy in surface_z
        if surface_terrain.get(xy) == terrain_key and xy not in hydro_xy
    }


def _place_consumer(
    surface_z: dict[Coord, int],
    base_z: Mapping[Coord, int],
    host: set[Coord],
    policy: HillPolicy,
    *,
    seed: int,
    salt: int,
    z_min: int,
    z_max: int,
) -> None:
    if not host:
        return
    spacing = int(policy.min_spacing)
    radius = int(policy.radius)
    height = int(policy.height)
    if spacing < 1 or radius < 1 or height < 1:
        return
    xs = [x for x, _ in surface_z]
    ys = [y for _, y in surface_z]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    placed: list[Coord] = []
    spacing2 = spacing * spacing
    for gy in range(y_min, y_max + 1, spacing):
        for gx in range(x_min, x_max + 1, spacing):
            ox = gx + _hash32(seed, gx, gy, salt) % spacing
            oy = gy + _hash32(seed, gx, gy, salt ^ 0x9E3779B9) % spacing
            origin = (ox, oy)
            if origin not in host:
                continue
            if any(
                (ox - px) * (ox - px) + (oy - py) * (oy - py) < spacing2
                for px, py in placed
            ):
                continue
            pool = policy.resolved_shapes()
            shape = pool[_hash32(seed, ox, oy, salt ^ 0xA5A5A5A5) % len(pool)]
            axis = _hash32(seed, ox, oy, salt ^ 0x3C6EF35A) % 2
            delta = raster_hill(
                origin,
                radius=radius,
                height=height,
                host_cells=host,
                shape=shape,
                axis=axis,
            )
            if delta is None:
                continue
            placed.append(origin)
            for xy, dz in delta.items():
                lifted = base_z[xy] + dz
                surface_z[xy] = max(z_min, min(z_max, max(surface_z[xy], lifted)))


def _hash32(seed: int, x: int, y: int, salt: int) -> int:
    return (int(seed) ^ (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF


def _salt(key: str) -> int:
    h = 2166136261
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h
