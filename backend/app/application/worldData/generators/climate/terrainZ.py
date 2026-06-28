"""Elevation → terrain type mapping for surface cells (CL-12)."""


def z_to_terrain(z: int, terrain_set: set[str]) -> str:
    if z >= 2:
        candidates = ["tundra", "plains"]
    elif z == 1:
        candidates = ["forest", "plains"]
    elif z == 0:
        candidates = ["plains"]
    else:
        candidates = ["liquid_body", "plains"]
    for t in candidates:
        if t in terrain_set:
            return t
    return next(iter(terrain_set), "plains")
