"""Resolve city dominant_material from generated layout (post-assemble)."""

from __future__ import annotations

import logging
from collections import Counter
from random import Random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import SettlementLayout
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.db.models.mapCell import MapCell
from app.db.models.world import World

from app.dataModel.materials import DEFAULT_DOMINANT_MATERIAL

logger = logging.getLogger(__name__)

_USE_TYPE = "wall"


def _append_cell_materials(materials: list[str], cells: list[MapCell]) -> None:
    for cell in cells:
        if cell.system_material:
            materials.append(cell.system_material)


def _append_structure_materials(materials: list[str], layout: StructureLayout) -> None:
    _append_cell_materials(materials, layout.cells)


def _materials_in_district(district: DistrictLayout) -> list[str]:
    materials: list[str] = []
    for edge in district.connection_edges:
        if edge.material:
            materials.append(edge.material)
    _append_cell_materials(materials, district.barrier_cells)
    for area in district.area_layouts:
        _append_cell_materials(materials, area.barrier_cells)
        _append_structure_materials(materials, area.building_layout)
        for small in area.small_layouts:
            _append_structure_materials(materials, small)
    return materials


def _city_level_materials(layout: SettlementLayout) -> list[str]:
    materials: list[str] = []
    for edge in layout.connection_edges:
        if edge.material:
            materials.append(edge.material)
    _append_cell_materials(materials, layout.barrier_cells)
    return materials


def _mode(materials: list[str]) -> str | None:
    if not materials:
        return None
    counts = Counter(materials)
    top_count = max(counts.values())
    winners = sorted(m for m, c in counts.items() if c == top_count)
    return winners[0]


def _district_dominants(layout: SettlementLayout) -> list[str]:
    dominants: list[str] = []
    for district in layout.district_layouts:
        dominant = _mode(_materials_in_district(district))
        if dominant:
            dominants.append(dominant)
    return dominants


def _default_from_economic_tier(
    world: World,
    economic_tier: str,
    rng: Random,
) -> str:
    return resolve_material(
        world,
        _USE_TYPE,
        economic_tier,
        rng,
        DEFAULT_DOMINANT_MATERIAL,
    )


def resolve_dominant_material(
    world: World,
    layout: SettlementLayout,
    skeleton: CitySkeleton,
    *,
    settlement_uid: str = "",
) -> str:
    """
    После assemble: доминирующий материал города для LLM.

    1. По каждому району — mode материалов из layout (edges.material, MapCell.system_material).
    2. Город — mode district-dominants; если районов без материалов — mode city-level (стены, дороги).
    3. Fallback: economic_tier → material_registry (wall).
    4. Fallback: hard default + warn_once.
    """
    district_modes = _district_dominants(layout)
    if district_modes:
        resolved = _mode(district_modes)
        if resolved:
            logger.info(
                "resolve_dominant_material | settlement=%s source=districts material=%r"
                " district_modes=%s",
                settlement_uid,
                resolved,
                district_modes,
            )
            return resolved

    city_level = _city_level_materials(layout)
    if city_level:
        resolved = _mode(city_level)
        if resolved:
            logger.info(
                "resolve_dominant_material | settlement=%s source=city_level material=%r",
                settlement_uid,
                resolved,
            )
            return resolved

    tier = skeleton.economic_tier
    if tier:
        rng = Random(f"{world.world_uid}_{settlement_uid}_dominant_material")
        resolved = _default_from_economic_tier(world, tier, rng)
        logger.info(
            "resolve_dominant_material | settlement=%s source=economic_tier tier=%r material=%r",
            settlement_uid,
            tier,
            resolved,
        )
        return resolved

    warn_once(
        world.world_uid,
        "dominant_material_no_tier",
        "resolve_dominant_material: no layout materials and no economic_tier for settlement=%s,"
        " using fallback %r",
        settlement_uid,
        DEFAULT_DOMINANT_MATERIAL,
    )
    return DEFAULT_DOMINANT_MATERIAL
