"""L2 open-land hills — raster helper + plains/forest placement.

SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
"""

from app.application.worldData.generators.terrain.hills.hillPlacement import (
    place_hills,
)
from app.application.worldData.generators.terrain.hills.hillRaster import (
    raster_hill,
)

__all__ = ["place_hills", "raster_hill"]
