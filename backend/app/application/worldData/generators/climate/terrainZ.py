"""Re-export skeleton terrain mapping from terrain module."""

from app.application.worldData.generators.terrain.terrainZ import (  # noqa: F401
    surface_terrain_at_z,
    subsurface_terrain_at_z,
    z_to_terrain,
)
