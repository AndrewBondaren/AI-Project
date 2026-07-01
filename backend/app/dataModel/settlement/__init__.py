"""
SCH-WORLD-SETTLEMENT — settlement stack master data.

Subdomains: settlement (city registries + skeleton), district, area.
Эталон: docs/tz_city_generation.md, docs/tz_assembler_hierarchy.md.
"""

from app.dataModel.settlement.area import PerimeterBarrier
from app.dataModel.settlement.enums import (
    DEFAULT_BLOCK_SIZE_M,
    DistrictDensity,
    block_size_for_density,
)
from app.dataModel.settlement.district import (
    DistrictConnection,
    DistrictTemplateEntry,
    PlacementCondition,
    RequiredStructure,
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.settlement import (
    CitySizeEntry,
    LocationMoodEntry,
    SettlementSkeleton,
    WorldCitySizeRegistry,
    WorldLocationMoodRegistry,
)

__all__ = [
    "CitySizeEntry",
    "DEFAULT_BLOCK_SIZE_M",
    "DistrictConnection",
    "DistrictDensity",
    "DistrictTemplateEntry",
    "LocationMoodEntry",
    "PerimeterBarrier",
    "PlacementCondition",
    "RequiredStructure",
    "SettlementSkeleton",
    "WorldCitySizeRegistry",
    "WorldDistrictTemplateRegistry",
    "WorldLocationMoodRegistry",
    "block_size_for_density",
]
