"""Ocean bathymetry — stub elevation now; DepressionForm pipeline later.

See docs/tz_terrain_hydrology.md § Ocean bathymetry / Depression forms.
"""

from app.application.worldData.generators.hydrology.bathymetry.stubElevation import (
    ocean_stub_drop_amount,
    resolve_open_water_surface_z,
)

__all__ = [
    "ocean_stub_drop_amount",
    "resolve_open_water_surface_z",
]
