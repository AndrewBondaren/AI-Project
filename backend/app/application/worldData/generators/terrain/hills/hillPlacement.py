"""Hill consumers — each registered terrain independently.

Helper is ``hillRaster.raster_hill``. This module places origins
(``min_spacing``) and applies ``Δz``. Does not load world JSON.
SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from app.application.worldData.generators.terrain.hills.hillRaster import Coord
from app.application.worldData.generators.terrain.hills.hillSelection import selected_hills, _salt
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrainMasks.hillPolicy import HillPolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def place_hills(
    surface_z: dict[Coord, int],
    surface_terrain: Mapping[Coord, str],
    excluded_cells: Collection[Coord],
    *,
    terrain_registry: WorldTerrainRegistry,
    seed: int,
    z_min: int,
    z_max: int,
) -> None:
    """Mutate ``surface_z`` in place. ``system_terrain`` is not written.

    Host = supplied cells with that consumer's terrain key
    and outside explicit exclusions. Skip the whole hill if its footprint does not fit.
    Exclusion ownership belongs to the caller's stage; no water facts are read here.
    ``z_band`` is not applied here.
    """
    if not surface_z:
        return
    excluded = frozenset(excluded_cells)
    base_z = dict(surface_z)
    for key in sorted(set(surface_terrain.values())):
        entry = terrain_registry.entry_for(key)
        if entry is None or entry.hills is None:
            continue
        _place_consumer(
            surface_z,
            base_z,
            _host_for(surface_z, surface_terrain, excluded, key),
            entry.hills,
            seed=seed,
            salt=_salt(key),
            z_min=z_min,
            z_max=z_max,
        )



def _host_for(
    surface_z: Mapping[Coord, int],
    surface_terrain: Mapping[Coord, str],
    excluded_cells: frozenset[Coord],
    terrain_key: str,
) -> set[Coord]:
    return {
        xy
        for xy in surface_z
        if surface_terrain.get(xy) == terrain_key and xy not in excluded_cells
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
    if not surface_z:
        return
    bounds = GridBBox(min(x for x, _ in surface_z), max(x for x, _ in surface_z),
                      min(y for _, y in surface_z), max(y for _, y in surface_z))
    for _, _, _, delta in selected_hills(bounds, host, policy, seed=seed, salt=salt):
        for xy, dz in delta.items():
            lifted = base_z[xy] + dz
            surface_z[xy] = max(z_min, min(z_max, max(surface_z[xy], lifted)))
