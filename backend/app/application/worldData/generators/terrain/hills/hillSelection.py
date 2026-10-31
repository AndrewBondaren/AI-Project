"""Canonical existing greedy hill selection, independent of fine height values."""
from collections.abc import Collection, Iterator, Mapping
from typing import Literal

from app.application.worldData.generators.terrain.hills.hillRaster import Coord, raster_hill
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.hills.acceptedHill import AcceptedHill
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.hillShape import HillShape
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def prepare_hills(bounds: GridBBox, terrain: Mapping[Coord, str], excluded: Collection[Coord], *,
                  registry: WorldTerrainRegistry, seed: int) -> tuple[AcceptedHill, ...]:
    result = []
    for key in sorted(set(terrain.values())):
        entry = registry.entry_for(key)
        if entry is not None and entry.hills is not None:
            host = {cell for cell, value in terrain.items() if value == key and cell not in excluded}
            for origin, shape, axis, _ in selected_hills(bounds, host, entry.hills, seed=seed, salt=_salt(key)):
                result.append(AcceptedHill(origin=(FineX(origin[0]), FineY(origin[1])),
                    radius=int(entry.hills.radius), height=int(entry.hills.height), shape=shape, axis=axis))
    return tuple(result)


def selected_hills(bounds: GridBBox, host: set[Coord], policy: HillPolicy, *,
                   seed: int, salt: int) -> Iterator[tuple[Coord, HillShape, Literal[0, 1], dict[Coord, int]]]:
    if not host:
        return
    spacing = int(policy.min_spacing)
    radius = int(policy.radius)
    height = int(policy.height)
    if spacing < 1 or radius < 1 or height < 1:
        return
    x_min, x_max = bounds.x_min, bounds.x_max
    y_min, y_max = bounds.y_min, bounds.y_max
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
            axis: Literal[0, 1] = 0 if _hash32(seed, ox, oy, salt ^ 0x3C6EF35A) % 2 == 0 else 1
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
            yield origin, shape, axis, delta


def _hash32(seed: int, x: int, y: int, salt: int) -> int:
    return (int(seed) ^ (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF


def _salt(key: str) -> int:
    h = 2166136261
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h
