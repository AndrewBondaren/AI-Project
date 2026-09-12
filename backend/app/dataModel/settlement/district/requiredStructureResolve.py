"""Resolve district pins and settlement purpose rows to catalog layouts."""

from __future__ import annotations

from collections.abc import Sequence

from app.dataModel.settlement.district.allowedStructureTypes import district_hosts_purpose
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.enums.buildingPurpose import (
    AllowedToken,
    BuildingPurpose,
)


def resolve_required_layouts(
    required: RequiredStructure,
    catalog: BuildingCatalog,
) -> tuple[BuildingLayoutTemplate, ...]:
    """Settlement recipe: pool by purpose. District row: pin ``building_template``."""
    if required.structure_type is not None:
        return catalog.of_structure_type(required.structure_type)
    layout = catalog.by_system_name(required.building_template)
    if layout is None:
        return ()
    return (layout,)


def _row_key(req: RequiredStructure) -> str:
    if req.structure_type is not None:
        return str(req.structure_type)
    return req.building_template


def union_required_structures(
    settlement_structure_types: Sequence[str],
    district_required: Sequence[RequiredStructure],
    allowed_structure_types: Sequence[AllowedToken] | None = None,
    enabled: Sequence[BuildingPurpose] | None = None,
) -> list[RequiredStructure]:
    """Settlement recipe types this district hosts, then district pins; first key wins."""
    out: list[RequiredStructure] = []
    seen: set[str] = set()
    for type_name in settlement_structure_types:
        purpose = BuildingPurpose.from_wire(type_name)
        if purpose is None:
            continue
        if not district_hosts_purpose(allowed_structure_types, purpose, enabled):
            continue
        key = str(purpose)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            RequiredStructure(
                building_template=key,
                structure_type=purpose,
            )
        )
    for req in district_required:
        key = _row_key(req)
        if key in seen:
            continue
        seen.add(key)
        out.append(req)
    return out


def unhosted_settlement_types(
    settlement_structure_types: Sequence[str],
    district_alloweds: Sequence[Sequence[AllowedToken] | None],
    enabled: Sequence[BuildingPurpose] | None = None,
) -> tuple[str, ...]:
    """Settlement purposes with no host district (leftover + warning)."""
    leftover: list[str] = []
    seen: set[str] = set()
    for type_name in settlement_structure_types:
        purpose = BuildingPurpose.from_wire(type_name)
        key = str(purpose) if purpose is not None else str(type_name).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        if purpose is None:
            leftover.append(key)
            continue
        if any(
            district_hosts_purpose(allowed, purpose, enabled)
            for allowed in district_alloweds
        ):
            continue
        leftover.append(key)
    return tuple(leftover)
