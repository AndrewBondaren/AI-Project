"""Stub ore placement — independent of skeleton depth (Phase 4)."""

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.masterData import material_rows
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def generate_ores(world: World, cells: list[MapCell]) -> list[MapCell]:
    """Mark ~3% of subsurface cells with system_material=iron when available."""
    material_keys = {
        m["system_material"]
        for m in material_rows(world)
        if m.get("system_material")
    }
    ore_mat = "iron" if "iron" in material_keys else next(iter(material_keys), None)
    if ore_mat is None:
        return []

    seed = world_seed(world)
    out: list[MapCell] = []
    surface_z: dict[tuple[int, int], int] = {}
    for c in cells:
        key = (c.x, c.y)
        if key not in surface_z or c.z > surface_z[key]:
            surface_z[key] = c.z

    for c in cells:
        sz = surface_z.get((c.x, c.y))
        if sz is None or c.z >= sz:
            continue
        h = (seed ^ (c.x * 92837111) ^ (c.y * 689287499) ^ (c.z * 283923481)) & 0xFFFFFFFF
        if h % 100 < 3:
            out.append(MapCell(
                world_uid=c.world_uid,
                x=c.x,
                y=c.y,
                z=c.z,
                system_material=ore_mat,
            ))
    return out
