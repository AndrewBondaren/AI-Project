"""
effective_travel_modifier и road tier stats — tz_structure_connections.md §3.7.
Вычисляется at runtime; на ConnectionEdge не persist'ится.
"""

from __future__ import annotations

from app.application.worldData.generators.utils.tierRegistry import tier_entry
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.world import World

# fallback если economic_tier_registry без road_tier_* (TZ §3.7)
_DEFAULT_ROAD_TIER_BONUS: dict[str, float] = {
    "poor":        1.20,
    "basic":       1.10,
    "standard":    1.00,
    "premium":     0.95,
    "quality":     0.95,
    "exceptional": 0.90,
}

_DEFAULT_ROAD_TIER_DURABILITY: dict[str, float] = {
    "poor":        0.6,
    "basic":       0.8,
    "standard":    1.0,
    "premium":     1.3,
    "quality":     1.3,
    "exceptional": 1.6,
}

_DEFAULT_BASE_TRAVEL_MODIFIER = 1.0
_DEFAULT_CONDITION_DEGRADATION = 0.2


def _material_entry(world: World, system_material: str | None) -> dict | None:
    if not system_material:
        return None
    for entry in world.material_registry or []:
        if entry.get("system_material") == system_material:
            return entry
    return None


def material_economic_tier(world: World, system_material: str | None) -> str | None:
    entry = _material_entry(world, system_material)
    if entry is None:
        return None
    tier = entry.get("economic_tier")
    return str(tier) if tier else None


def resolve_road_tier_bonus(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return 1.0
    entry = tier_entry(world.economic_tier_registry, material_tier)
    if entry is not None:
        val = entry.get("road_tier_bonus")
        if val is not None:
            return float(val)
    return _DEFAULT_ROAD_TIER_BONUS.get(material_tier, 1.0)


def resolve_road_tier_durability(world: World, material_tier: str | None) -> float:
    if not material_tier:
        return 1.0
    entry = tier_entry(world.economic_tier_registry, material_tier)
    if entry is not None:
        val = entry.get("road_tier_durability")
        if val is not None:
            return float(val)
    return _DEFAULT_ROAD_TIER_DURABILITY.get(material_tier, 1.0)


def _road_settings_entry(world: World, connection_type: str) -> dict | None:
    settings = getattr(world, "road_settings", None) or []
    if isinstance(settings, dict):
        settings = settings.get("entries") or settings.get(connection_type)
        if isinstance(settings, dict):
            return settings
        return None
    for entry in settings:
        if entry.get("system_connection_type") == connection_type:
            return entry
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
    strength = float(mat_entry.get("structural_strength", 1.0)) if mat_entry else 1.0
    denom = durability * max(strength, 0.01)
    return base_degradation / denom
