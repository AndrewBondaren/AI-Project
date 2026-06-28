"""Stub cave carve — does not overwrite ore markers (Phase 4)."""

from app.application.worldData.generators.climate.math import world_seed
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def generate_caves(world: World, cells: list[MapCell]) -> list[MapCell]:
    """Carve ~1% subsurface cells to open_space; skip cells with ore material."""
    terrain_set = {
        t["system_terrain"] for t in (world.terrain_registry or []) if "system_terrain" in t
    }
    cave_type = "open_space" if "open_space" in terrain_set else None
    if cave_type is None:
        return []

    seed = world_seed(world)
    out: list[MapCell] = []
    surface_z: dict[tuple[int, int], int] = {}
    for c in cells:
        key = (c.x, c.y)
        if key not in surface_z or c.z > surface_z[key]:
            surface_z[key] = c.z

    for c in cells:
        if c.system_material is not None:
            continue
        sz = surface_z.get((c.x, c.y))
        if sz is None or c.z >= sz:
            continue
        h = (seed ^ (c.x * 1234567) ^ (c.y * 7654321) ^ (c.z * 987654321)) & 0xFFFFFFFF
        if h % 100 < 1:
            out.append(MapCell(
                world_uid=c.world_uid,
                x=c.x,
                y=c.y,
                z=c.z,
                system_terrain=cave_type,
            ))
    return out
