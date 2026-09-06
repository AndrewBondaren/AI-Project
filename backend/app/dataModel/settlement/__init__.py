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
    CellZone,
    DistrictConnection,
    DistrictTemplateEntry,
    DistrictTopologyEntry,
    DistrictTopologySlot,
    DistrictZonePreferenceEntry,
    FrontageTypeOrder,
    PRIORITY_WITHOUT_KEY,
    PlacementCondition,
    PlacementConditionType,
    RequiredStructure,
    WorldDistrictTemplateRegistry,
    WorldDistrictZonePreference,
    allowed_fill_structure_types,
    resolve_frontage_type_order,
    resolve_required_layouts,
    resolve_structure_count,
    resolve_structure_priority,
    union_required_structures,
)
from app.dataModel.settlement.settlement import (
    CitySizeEntry,
    LocationMoodEntry,
    SettlementSkeleton,
    SettlementSpecializationBind,
    SettlementSpecializationEntry,
    TypicalDistrictRef,
    WorldCitySizeRegistry,
    WorldLocationMoodRegistry,
    WorldSettlementSpecializationRegistry,
)

__all__ = [
    "CellZone",
    "CitySizeEntry",
    "DEFAULT_BLOCK_SIZE_M",
    "DistrictConnection",
    "DistrictDensity",
    "DistrictTemplateEntry",
    "DistrictTopologyEntry",
    "DistrictTopologySlot",
    "DistrictZonePreferenceEntry",
    "FrontageTypeOrder",
    "LocationMoodEntry",
    "COUNT_WITHOUT_KEY",
    "PRIORITY_WITHOUT_KEY",
    "PerimeterBarrier",
    "PlacementCondition",
    "PlacementConditionType",
    "RequiredStructure",
    "SettlementSkeleton",
    "SettlementSpecializationBind",
    "SettlementSpecializationEntry",
    "TypicalDistrictRef",
    "WorldCitySizeRegistry",
    "WorldDistrictTemplateRegistry",
    "WorldDistrictZonePreference",
    "WorldLocationMoodRegistry",
    "WorldSettlementSpecializationRegistry",
    "allowed_fill_structure_types",
    "block_size_for_density",
    "resolve_frontage_type_order",
    "resolve_required_layouts",
    "resolve_structure_count",
    "resolve_structure_priority",
    "resolved_host_sides",
    "union_required_structures",
]
