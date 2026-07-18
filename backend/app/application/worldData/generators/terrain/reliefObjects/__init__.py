"""Pass 1.4 relief objects — mountain rise / ravine drop on surface heightmap.

``apply_relief_objects_z`` mutates ``heightmap.surface_z`` in place and returns
the same ``SurfaceHeightmap`` instance.
"""

from app.application.worldData.generators.terrain.reliefObjects.applyReliefObjectsZ import (
    apply_relief_objects_z,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    mountain_rise_amount,
    resolve_mountain_surface_z,
    resolve_ravine_surface_z,
)

__all__ = [
    "apply_relief_objects_z",
    "mountain_rise_amount",
    "resolve_mountain_surface_z",
    "resolve_ravine_surface_z",
]
