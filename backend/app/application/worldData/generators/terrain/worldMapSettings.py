"""World map generation settings — single read path for terrain/climate bbox and persist tuning."""

from app.application.jsonValidation import terrain_scalars
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.db.models.world import World

DEFAULT_GRID_BBOX_PADDING = 2
MIN_MAP_SUBSURFACE_DEPTH = 0

_terrain_defaults = WorldTerrainScalars.canonical_defaults()
DEFAULT_TERRAIN_CHUNK_COLUMNS = _terrain_defaults.terrain_chunk_columns or 32
DEFAULT_MAP_SUBSURFACE_DEPTH = (
    _terrain_defaults.map_subsurface_depth
    if _terrain_defaults.map_subsurface_depth is not None
    else 0
)
DEFAULT_Z_MIN = WorldTerrainScalars.resolved_z_min(None)
DEFAULT_Z_MAX = WorldTerrainScalars.resolved_z_max(None)
SERIAL_TERRAIN_CELL_THRESHOLD = 50_000


def grid_bbox_padding(world: World) -> int:
    """Grid cells added around static anchor bbox (v1 materialization extent)."""
    v = world.grid_bbox_padding
    if v is None or v < 0:
        return DEFAULT_GRID_BBOX_PADDING
    return v


def terrain_chunk_columns(world: World) -> int:
    """Column-fill persist batch size (square chunk side in grid cells)."""
    v = terrain_scalars(world).terrain_chunk_columns
    if v is None or v < 1:
        return DEFAULT_TERRAIN_CHUNK_COLUMNS
    return v


def n_base(world: World) -> int:
    """Skeleton subsurface band under flat ground (0 = surface-only; cliffs use N_eff)."""
    depth = terrain_scalars(world).map_subsurface_depth
    if depth is None:
        depth = DEFAULT_MAP_SUBSURFACE_DEPTH
    return max(MIN_MAP_SUBSURFACE_DEPTH, depth)


def world_z_min(world: World) -> int:
    """Vertical lower bound for skeleton columns (meters / 100 per z level)."""
    return WorldTerrainScalars.resolved_z_min(terrain_scalars(world).z_min)


def world_z_max(world: World) -> int:
    """Vertical upper bound for surface heightmap clamp."""
    return WorldTerrainScalars.resolved_z_max(terrain_scalars(world).z_max)


def force_serial_terrain_generate(world: World, surface_column_count: int) -> bool:
    """TZ TR-PAR: skip pool overhead on small tile/column counts."""
    if surface_column_count <= 0:
        return True
    return surface_column_count * (1 + n_base(world)) < SERIAL_TERRAIN_CELL_THRESHOLD
