"""Wire street layout keys — tz_structure_connections.md."""

from __future__ import annotations

from enum import StrEnum

#Todo for streets
class StreetLayout(StrEnum):
    GRID = "grid"
    ORGANIC = "organic"
    RADIAL = "radial"
    CUL_DE_SAC = "cul_de_sac"
    COURTYARD = "courtyard"
