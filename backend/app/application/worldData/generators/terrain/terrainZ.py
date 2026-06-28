"""Elevation → terrain type mapping for skeleton cells (solid only; no liquid)."""


def _pick(candidates: list[str], terrain_set: set[str]) -> str:
    for t in candidates:
        if t in terrain_set:
            return t
    return next(iter(terrain_set), "plains")


def surface_terrain_at_z(z: int, terrain_set: set[str]) -> str:
    if z >= 2:
        candidates = ["tundra", "plains"]
    elif z == 1:
        candidates = ["forest", "plains"]
    else:
        candidates = ["plains"]
    return _pick(candidates, terrain_set)


def subsurface_terrain_at_z(terrain_set: set[str]) -> str:
    return _pick(["earth", "plains"], terrain_set)


def magma_terrain(terrain_set: set[str]) -> str:
    if "magma" in terrain_set:
        return "magma"
    return subsurface_terrain_at_z(terrain_set)


def z_to_terrain(z: int, terrain_set: set[str]) -> str:
    """Backward-compat alias — surface mapping only (no liquid_body by z)."""
    return surface_terrain_at_z(z, terrain_set)
