"""World map generation settings — single read path for terrain/climate bbox and persist tuning."""

from app.db.models.world import World

DEFAULT_GRID_BBOX_PADDING = 2
DEFAULT_TERRAIN_CHUNK_COLUMNS = 32
DEFAULT_MAP_SUBSURFACE_DEPTH = 20
MIN_MAP_SUBSURFACE_DEPTH = 10
DEFAULT_Z_MIN = -8000
DEFAULT_Z_MAX = 8000


def grid_bbox_padding(world: World) -> int:
    """Grid cells added around static anchor bbox (v1 materialization extent)."""
    v = world.grid_bbox_padding
    if v is None or v < 0:
        return DEFAULT_GRID_BBOX_PADDING
    return v


def terrain_chunk_columns(world: World) -> int:
    """Column-fill persist batch size (square chunk side in grid cells)."""
    v = world.terrain_chunk_columns
    if v is None or v < 1:
        return DEFAULT_TERRAIN_CHUNK_COLUMNS
    return v


def n_base(world: World) -> int:
    """Minimum subsurface band depth N_base before cliff compensation."""
    depth = world.map_subsurface_depth
    if depth is None:
        depth = DEFAULT_MAP_SUBSURFACE_DEPTH
    return max(MIN_MAP_SUBSURFACE_DEPTH, depth)


def world_z_min(world: World) -> int:
    """Vertical lower bound for skeleton columns (meters / 100 per z level)."""
    if world.z_min is not None:
        return world.z_min
    return DEFAULT_Z_MIN


def world_z_max(world: World) -> int:
    """Vertical upper bound for surface heightmap clamp."""
    if world.z_max is not None:
        return world.z_max
    return DEFAULT_Z_MAX

