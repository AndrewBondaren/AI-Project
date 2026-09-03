"""
SCH-WORLD-SETTLEMENT — settlement stack master data.

Subdomains: settlement (city registries + skeleton), district, area.
Эталон: docs/tz_city_generation.md, docs/tz_assembler_hierarchy.md.
"""

from app.dataModel.settlement.area import PerimeterBarrier, resolved_host_sides
from app.dataModel.settlement.enums import (
    DEFAULT_BLOCK_SIZE_M,
    DistrictDensity,
    block_size_for_density,
)
from app.dataModel.settlement.district import (
    COUNT_WITHOUT_KEY,
    DistrictConnection,
    DistrictTemplateEntry,
    FrontageTypeOrder,
    PRIORITY_WITHOUT_KEY,
    PlacementCondition,
    RequiredStructure,
    WorldDistrictTemplateRegistry,
    resolve_frontage_type_order,
    resolve_structure_count,
    resolve_structure_priority,
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
    "FrontageTypeOrder",
    "LocationMoodEntry",
    "COUNT_WITHOUT_KEY",
    "PRIORITY_WITHOUT_KEY",
    "PerimeterBarrier",
    "PlacementCondition",
    "RequiredStructure",
    "SettlementSkeleton",
    "WorldCitySizeRegistry",
    "WorldDistrictTemplateRegistry",
    "WorldLocationMoodRegistry",
    "block_size_for_density",
    "resolve_frontage_type_order",
    "resolve_structure_count",
    "resolve_structure_priority",
    "resolved_host_sides",
]
