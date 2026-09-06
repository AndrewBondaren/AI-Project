"""Build ``WorldRegistryIndex`` from normalized ``worlds`` wire dict.

После ``facade`` читаем wire dict напрямую — **без** повторного ``resolve_root_list`` /
``model_validate`` на POJO. Иначе второй проход падает на nullable полях с ``constrained_field``
(явный ``None`` в normalized dump + ``ge``/``gt`` на Field — тот же класс бага, что у
``elevation_lapse_rate`` в ``WorldTerrainScalars``). Import уже провалидирован; index нужен
только для REF-W lookup по ключам.
"""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.worldSlices import climate_zone_wire_from_raw, registry_map_to_list
from app.dataModel import (
    WorldClimateZoneRegistry,
    WorldEconomyTierRegistry,
    WorldMaterialRegistry,
    WorldTerrainRegistry,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.resources.worldResourceTypeRegistry import WorldResourceTypeRegistry
from app.dataModel.flora.worldCropsRegistry import WorldCropsRegistry
from app.dataModel.livestock.worldLivestockRegistry import WorldLivestockRegistry


def _registry_rows(
    normalized: dict[str, Any],
    world_key: str,
    *,
    partial: bool,
    wire_adapter: Any = None,
) -> list[dict[str, Any]] | None:
    if world_key not in normalized:
        return None if partial else [
            row.model_dump(mode="json")
            for row in _canonical_rows(world_key)
        ]
    raw = normalized.get(world_key)
    if wire_adapter is not None:
        raw = wire_adapter(raw)
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _canonical_rows(world_key: str) -> list[Any]:
    return {
        "material_registry": WorldMaterialRegistry.canonical_defaults().root,
        "terrain_registry": WorldTerrainRegistry.canonical_defaults().root,
        "climate_zone_registry": WorldClimateZoneRegistry.canonical_defaults().root,
        "economic_tier_registry": WorldEconomyTierRegistry.canonical_defaults().root,
        "connection_type_registry": WorldConnectionTypeRegistry.canonical_defaults().root,
        "resource_type_registry": WorldResourceTypeRegistry.canonical_defaults().root,
        "crops_registry": WorldCropsRegistry.canonical_defaults().root,
        "livestock_registry": WorldLivestockRegistry.canonical_defaults().root,
    }[world_key]


def _material_keys(rows: list[dict[str, Any]]) -> tuple[frozenset[str], frozenset[str]]:
    materials: set[str] = set()
    liquids: set[str] = set()
    for row in rows:
        key = row.get("system_material")
        if not key:
            continue
        materials.add(str(key))
        category = row.get("material_category")
        if category == MaterialCategory.LIQUID or category == MaterialCategory.LIQUID.value:
            liquids.add(str(key))
    return frozenset(materials), frozenset(liquids)


def _row_keys(rows: list[dict[str, Any]], field: str) -> frozenset[str]:
    return frozenset(
        str(row[field])
        for row in rows
        if row.get(field) is not None
    )


def build_world_registry_index(
    normalized: dict[str, Any],
    *,
    partial: bool,
) -> WorldRegistryIndex:
    """REF-W vocabularies from post-``facade`` wire — wire rows only, no second resolve."""
    material_rows = _registry_rows(normalized, "material_registry", partial=partial) or []
    terrain_rows = _registry_rows(normalized, "terrain_registry", partial=partial) or []
    climate_rows = _registry_rows(
        normalized,
        "climate_zone_registry",
        partial=partial,
        wire_adapter=climate_zone_wire_from_raw,
    ) or []
    tier_rows = _registry_rows(normalized, "economic_tier_registry", partial=partial) or []
    conn_rows = _registry_rows(normalized, "connection_type_registry", partial=partial) or []
    resource_rows = _registry_rows(
        normalized,
        "resource_type_registry",
        partial=partial,
        wire_adapter=lambda raw: registry_map_to_list(raw, id_field="system_resource"),
    ) or []
    crop_rows = _registry_rows(
        normalized,
        "crops_registry",
        partial=partial,
        wire_adapter=lambda raw: registry_map_to_list(raw, id_field="system_crop"),
    ) or []
    livestock_rows = _registry_rows(
        normalized,
        "livestock_registry",
        partial=partial,
        wire_adapter=lambda raw: registry_map_to_list(raw, id_field="system_livestock"),
    ) or []

    materials, liquids = _material_keys(material_rows) if material_rows else (None, None)
    if partial and "material_registry" not in normalized:
        materials, liquids = None, None

    return WorldRegistryIndex(
        materials=materials,
        liquids=liquids,
        terrains=(
            _row_keys(terrain_rows, "system_terrain")
            if terrain_rows or not partial
            else None
        ),
        climate_zones=(
            _row_keys(climate_rows, "system_climate")
            if climate_rows or not partial
            else None
        ),
        economic_tiers=(
            _row_keys(tier_rows, "system_tier")
            if tier_rows or not partial
            else None
        ),
        connection_types=(
            _row_keys(conn_rows, "system_connection_type")
            if conn_rows or not partial
            else None
        ),
        resources=(
            _row_keys(resource_rows, "system_resource")
            if resource_rows or not partial
            else None
        ),
        crops=(
            _row_keys(crop_rows, "system_crop")
            if crop_rows or not partial
            else None
        ),
        livestock=(
            _row_keys(livestock_rows, "system_livestock")
            if livestock_rows or not partial
            else None
        ),
    )
