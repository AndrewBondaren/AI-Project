"""Resolve district/settlement required rows to catalog layouts (CITY-T-2d)."""

from __future__ import annotations

from collections.abc import Sequence

from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate


def resolve_required_layouts(
    required: RequiredStructure,
    catalog: BuildingCatalog,
) -> tuple[BuildingLayoutTemplate, ...]:
    """Type pool, else ``building_template`` as type, else as ``system_name``."""
    if required.structure_type:
        return catalog.of_structure_type(required.structure_type)
    as_type = catalog.of_structure_type(required.building_template)
    if as_type:
        return as_type
    layout = catalog.by_system_name(required.building_template)
    if layout is None:
        return ()
    return (layout,)


def union_required_structures(
    settlement_structure_types: Sequence[str],
    district_required: Sequence[RequiredStructure],
) -> list[RequiredStructure]:
    """Settlement recipe types first, then district rows; first key wins."""
    out: list[RequiredStructure] = []
    seen: set[str] = set()
    for type_name in settlement_structure_types:
        if type_name in seen:
            continue
        seen.add(type_name)
        out.append(
            RequiredStructure(
                building_template=type_name,
                structure_type=type_name,
            )
        )
    for req in district_required:
        key = req.structure_type or req.building_template
        if key in seen:
            continue
        seen.add(key)
        out.append(req)
    return out
