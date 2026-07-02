"""
effective_travel_modifier и road tier stats — tz_structure_connections.md §3.7.
Вычисляется at runtime; на ConnectionEdge не persist'ится.
"""

from __future__ import annotations

from app.application.jsonValidation import (
    economic_tier_engine,
    economic_tiers,
    materials,
    road_settings,
)
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.world import World

_ENGINE_TIERS = economic_tier_engine()
_FALLBACK_ROAD = RoadSettingsEntry.fallback()
_FALLBACK_TIER = EconomyTierEntry.fallback()


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


def _economy_tier_entry(world: World, material_tier: str) -> EconomyTierEntry:
    entry = economic_tiers(world).entry_for(material_tier)
    if entry is not None:
        return entry
    engine = _ENGINE_TIERS.entry_for(material_tier)
    if engine is not None:
        return engine
    return _FALLBACK_TIER


def resolve_road_tier_bonus(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return float(_FALLBACK_TIER.road_tier_bonus)
    return float(_economy_tier_entry(world, material_tier).road_tier_bonus)


def resolve_road_tier_durability(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return float(_FALLBACK_TIER.road_tier_durability)
    return float(_economy_tier_entry(world, material_tier).road_tier_durability)


def resolve_base_travel_modifier(world: World, connection_type: str) -> float:
    entry = road_settings(world).entry_for(connection_type)
    if entry is not None:
        return float(entry.base_travel_modifier)
    return float(_FALLBACK_ROAD.base_travel_modifier)


def resolve_condition_degradation(world: World, connection_type: str) -> float:
    entry = road_settings(world).entry_for(connection_type)
    if entry is not None:
        return float(entry.condition_degradation)
    return float(_FALLBACK_ROAD.condition_degradation)


def condition_factor(edge: ConnectionEdge, degradation: float) -> float:
    condition = edge.condition if edge.condition is not None else 100
    return 1.0 + degradation * (1.0 - condition / 100.0)


def effective_travel_modifier(world: World, edge: ConnectionEdge) -> float:
    """
    base_travel_modifier × road_tier_bonus(material tier) × condition_factor.
    material=null → tier_bonus 1.0 (TZ §3.7).
    """
    if edge.material is None:
        tier_bonus = float(_FALLBACK_TIER.road_tier_bonus)
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
