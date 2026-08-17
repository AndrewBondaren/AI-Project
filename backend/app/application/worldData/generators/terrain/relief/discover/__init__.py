"""Relief pipeline v2 discover — R41 / C38–C41.

Application types, not persist. L2 volume stays in pack/refine paint.
"""

from app.application.worldData.generators.terrain.relief.discover.core import (
    discover_fronts,
    seed_rim,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    OpenLandPlugin,
    RavinePlugin,
    RoadShoulderPlugin,
    ShorePlugin,
    VertexBodyPlugin,
    plugins_for_keys,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
    FrontGeometry,
    GradePaintSpec,
    ReliefVertices,
)

__all__ = [
    "DiscoveredFront",
    "FrontGeometry",
    "GradePaintSpec",
    "OpenLandPlugin",
    "RavinePlugin",
    "ReliefVertices",
    "RoadShoulderPlugin",
    "ShorePlugin",
    "VertexBodyPlugin",
    "discover_fronts",
    "plugins_for_keys",
    "seed_rim",
]
