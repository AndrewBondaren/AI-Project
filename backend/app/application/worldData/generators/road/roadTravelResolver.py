"""
effective_travel_modifier и road tier stats — tz_structure_connections.md §3.7.
Вычисляется at runtime; на ConnectionEdge не persist'ится.
"""

from __future__ import annotations

from app.application.worldData.generators.masterData import (
    economic_tier_engine,
    economic_tier_rows,
    materials,
    road_settings,
)
from app.application.worldData.generators.utils.tierRegistry import tier_entry
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.world import World

_DEFAULT_BASE_TRAVEL_MODIFIER = 1.0
_DEFAULT_CONDITION_DEGRADATION = 0.2
_ENGINE_TIERS = economic_tier_engine()


def _material_entry(world: World, system_material: str | None):
    if not system_material:
        return None
    return materials(world).entry_for(system_material)


def material_economic_tier(world: World, system_material: str | None) -> str | None:
    entry = _material_entry(world, system_material)
    if entry is None:
        return None
    tier = entry.economic_tier
    return str(tier) if tier else None


def resolve_road_tier_bonus(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return 1.0
    entry = tier_entry(economic_tier_rows(world), material_tier)
    if entry is not None:
        val = entry.get("road_tier_bonus")
        if val is not None:
            return float(val)
    engine = _ENGINE_TIERS.entry_for(material_tier)
    if engine is not None:
        return float(engine.road_tier_bonus)
    return 1.0


def resolve_road_tier_durability(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return 1.0
    entry = tier_entry(economic_tier_rows(world), material_tier)
    if entry is not None:
        val = entry.get("road_tier_durability")
        if val is not None:
            return float(val)
    engine = _ENGINE_TIERS.entry_for(material_tier)
    if engine is not None:
        return float(engine.road_tier_durability)
    return 1.0


def _road_settings_entry(world: World, connection_type: str) -> dict | None:
    for entry in road_settings(world).root:
        if entry.system_connection_type == connection_type:
            return entry.model_dump(by_alias=True)
    return None


def resolve_base_travel_modifier(world: World, connection_type: str) -> float:
    entry = _road_settings_entry(world, connection_type)
    if entry is not None:
        val = entry.get("base_travel_modifier")
        if val is not None:
            return float(val)
    return _DEFAULT_BASE_TRAVEL_MODIFIER


def resolve_condition_degradation(world: World, connection_type: str) -> float:
    entry = _road_settings_entry(world, connection_type)
    if entry is not None:
        val = entry.get("condition_degradation")
        if val is not None:
            return float(val)
    return _DEFAULT_CONDITION_DEGRADATION


def condition_factor(edge: ConnectionEdge, degradation: float) -> float:
    condition = edge.condition if edge.condition is not None else 100
    return 1.0 + degradation * (1.0 - condition / 100.0)


def effective_travel_modifier(world: World, edge: ConnectionEdge) -> float:
    """
    base_travel_modifier × road_tier_bonus(material tier) × condition_factor.
    material=null → tier_bonus 1.0 (TZ §3.7).
    """
    if edge.material is None:
        tier_bonus = 1.0
    else:
        tier_bonus = resolve_road_tier_bonus(
            world, material_economic_tier(world, edge.material),
        )
    base = resolve_base_travel_modifier(world, edge.connection_type)
    degradation = resolve_condition_degradation(world, edge.connection_type)
    return base * tier_bonus * condition_factor(edge, degradation)


def effective_degradation_rate(
    world:            World,
    edge:             ConnectionEdge,
    base_degradation: float,
) -> float:
    """base_degradation / (road_tier_durability × material.structural_strength)."""
    if edge.material is None:
        return base_degradation
    mat_tier = material_economic_tier(world, edge.material)
    durability = resolve_road_tier_durability(world, mat_tier)
    mat_entry = _material_entry(world, edge.material)
    strength = float(mat_entry.structural_strength) if mat_entry and mat_entry.structural_strength else 1.0
    denom = durability * max(strength, 0.01)
    return base_degradation / denom
