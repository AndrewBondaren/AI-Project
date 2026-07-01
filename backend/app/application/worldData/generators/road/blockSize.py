"""Re-export district density / block size contract from dataModel."""

from app.dataModel.settlement.enums.districtDensity import (
    DEFAULT_BLOCK_SIZE_M,
    DistrictDensity,
    block_size_for_density,
)

BLOCK_SIZE_BY_DENSITY = DistrictDensity.block_size_map()
DEFAULT_BLOCK_SIZE = DEFAULT_BLOCK_SIZE_M

__all__ = [
    "BLOCK_SIZE_BY_DENSITY",
    "DEFAULT_BLOCK_SIZE",
    "DistrictDensity",
    "block_size_for_density",
]
