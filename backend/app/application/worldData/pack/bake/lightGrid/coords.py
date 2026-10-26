"""Temporary re-export of light-grid scale/coordinate symbols (PC-11.6a).

Canonical owners: ``dataModel/spatial/grid/lightGridScale`` and
``generators/coordinates/light/grid``. This alias delegates canonical
symbols — no second implementation — and resolves in PC-11.6b.
"""

from app.application.worldData.generators.coordinates.light.grid import (
    fine_to_light,
    fine_to_macro_local,
    light_cell_center_fine,
    light_cell_origin_fine,
    light_to_macro_local,
)
from app.dataModel.spatial.grid.lightGridScale import LightGridScale, light_span_for

__all__ = [
    "LightGridScale",
    "fine_to_light",
    "fine_to_macro_local",
    "light_cell_center_fine",
    "light_cell_origin_fine",
    "light_span_for",
    "light_to_macro_local",
]
