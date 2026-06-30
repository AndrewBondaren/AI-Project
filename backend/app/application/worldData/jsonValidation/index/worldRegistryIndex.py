"""Pass 1 index from world blob — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind

_DEFAULT_TERRAIN_CATEGORIES = frozenset({"solid", "liquid", "aerial", "crevice", "barrier"})

_ARRAY_REGISTRY_SPECS: tuple[tuple[RefKind, str, str], ...] = (
    (RefKind.MATERIAL, "material_registry", "system_material"),
    (RefKind.TERRAIN, "terrain_registry", "system_terrain"),
    (RefKind.TERRAIN_CAT, "terrain_category_registry", "system_category"),
    (RefKind.CLIMATE, "climate_zone_registry", "system_climate"),
    (RefKind.WEATHER, "weather_type_registry", "system_weather"),
    (RefKind.CONN, "connection_type_registry", "system_connection_type"),
    (RefKind.CITY_SIZE, "city_size_registry", "system_size"),
    (RefKind.ECON_TIER, "economic_tier_registry", "system_tier"),
    (RefKind.DANGER, "danger_level_registry", "system_danger"),
    (RefKind.CELL_STATE, "cell_state_registry", "system_state"),
    (RefKind.LOC_STATE, "location_state_registry", "system_state"),
    (RefKind.ROAD, "road_type_registry", "system_road_type"),
    (RefKind.PASSAGE, "passage_type_registry", "system_passage_type"),
    (RefKind.WOUND, "wound_type_registry", "system_wound_type"),
    (RefKind.COLOUR, "colour_registry", "system_colour"),
    (RefKind.TEXTURE, "texture_registry", "system_texture"),
    (RefKind.INTENSITY, "intensity_level_registry", "system_level"),
    (RefKind.NARR_TYPE, "narrative_type_registry", "system_type"),
    (RefKind.TRAIT, "character_trait_registry", "system_trait"),
    (RefKind.RESPAWN, "respawn_type_registry", "system_respawn_type"),
    (RefKind.NPC_TARGET, "npc_target_type_registry", "system_target_type"),
    (RefKind.NPC_NEED, "npc_needs_registry", "system_need_type"),
    (RefKind.NPC_GOAL, "npc_goal_type_registry", "system_goal_type"),
    (RefKind.RESOURCE, "resource_type_registry", "system_resource"),
    (RefKind.NPC_LLM_EVT, "npc_llm_event_type_registry", "system_event_type"),
)

_MAP_REGISTRY_SPECS: tuple[tuple[RefKind, str], ...] = (
    (RefKind.LORE, "lore_registry"),
    (RefKind.TAG, "tag_registry"),
    (RefKind.ROOM_TYPE, "room_type_registry"),
    (RefKind.BUILDING_TPL, "building_template_registry"),
    (RefKind.BARRIER_TPL, "barrier_template_registry"),
    (RefKind.BODY_SCHEMA, "body_schema_registry"),
    (RefKind.MAT_USE, "material_use_type_registry"),
    (RefKind.MAT_TAG, "material_tag_registry"),
    (RefKind.LIGHTING, "lighting_type_registry"),
)

_N1S_FIELDS: tuple[tuple[RefKind, str, str], ...] = (
    (RefKind.STAT, "stat_schema", "system_name"),
    (RefKind.SKILL, "skill_schema", "system_name"),
    (RefKind.RESIST, "resist_schema", "system_name"),
)


@dataclass
class WorldRegistryIndex:
    _keys: dict[RefKind, frozenset[str]] = field(default_factory=dict)

    def has_ref(self, ref: RefKind, key: str) -> bool:
        return key in self._keys.get(ref, frozenset())

    def keys(self, ref: RefKind) -> frozenset[str]:
        return self._keys.get(ref, frozenset())

    def register(self, ref: RefKind, key: str) -> None:
        if not key:
            return
        current = self._keys.get(ref, frozenset())
        self._keys[ref] = current | frozenset({key})

    def register_many(self, ref: RefKind, keys: set[str]) -> None:
        if not keys:
            return
        current = self._keys.get(ref, frozenset())
        self._keys[ref] = current | frozenset(keys)


def _array_keys(value: Any, key_field: str) -> set[str]:
    if not isinstance(value, list):
        return set()
    out: set[str] = set()
    for row in value:
        if isinstance(row, dict):
            k = row.get(key_field)
            if isinstance(k, str) and k:
                out.add(k)
    return out


def _map_keys(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    return {k for k in value if isinstance(k, str) and k}


def _location_type_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return _map_keys(value)
    if isinstance(value, list):
        return _array_keys(value, "system_type")
    return set()


def _location_subtype_keys(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for entry in value.values():
            if not isinstance(entry, dict):
                continue
            subtypes = entry.get("subtypes")
            if isinstance(subtypes, list):
                out |= _array_keys(subtypes, "system_subtype")
    elif isinstance(value, list):
        for entry in value:
            if not isinstance(entry, dict):
                continue
            subtypes = entry.get("subtypes")
            if isinstance(subtypes, list):
                out |= _array_keys(subtypes, "system_subtype")
    return out


def _n1s_keys(value: Any, key_field: str) -> set[str]:
    if isinstance(value, list):
        return _array_keys(value, key_field)
    if isinstance(value, dict):
        return _map_keys(value)
    return set()


def _liquid_material_keys(material_registry: Any) -> set[str]:
    if not isinstance(material_registry, list):
        return set()
    out: set[str] = set()
    for row in material_registry:
        if not isinstance(row, dict):
            continue
        if row.get("material_category") == "liquid":
            k = row.get("system_material")
            if isinstance(k, str) and k:
                out.add(k)
    return out


def _inline_terrain_categories(terrain_registry: Any) -> set[str]:
    if not isinstance(terrain_registry, list):
        return set()
    out: set[str] = set()
    for row in terrain_registry:
        if not isinstance(row, dict):
            continue
        cat = row.get("terrain_category")
        if isinstance(cat, str) and cat:
            out.add(cat)
    return out


def build_world_registry_index(world: dict[str, Any]) -> WorldRegistryIndex:
    index = WorldRegistryIndex()

    for ref_kind, field_name, key_field in _ARRAY_REGISTRY_SPECS:
        index.register_many(ref_kind, _array_keys(world.get(field_name), key_field))

    for ref_kind, field_name in _MAP_REGISTRY_SPECS:
        index.register_many(ref_kind, _map_keys(world.get(field_name)))

    loc_types = world.get("location_type_registry")
    index.register_many(RefKind.LOC_TYPE, _location_type_keys(loc_types))
    index.register_many(RefKind.LOC_SUBTYPE, _location_subtype_keys(loc_types))

    for ref_kind, field_name, key_field in _N1S_FIELDS:
        index.register_many(ref_kind, _n1s_keys(world.get(field_name), key_field))

    index.register_many(RefKind.MUSCLE_TBL, _array_keys(world.get("muscle_tables"), "table_id"))
    muscle_entries: set[str] = set()
    for row in world.get("muscle_tables") or []:
        if isinstance(row, dict) and isinstance(row.get("entries"), list):
            muscle_entries |= _array_keys(row["entries"], "system_muscle")
    index.register_many(RefKind.MUSCLE_TBL, muscle_entries)

    index.register_many(RefKind.CONSTIT_TBL, _array_keys(world.get("constitution_tables"), "table_id"))
    constit_entries: set[str] = set()
    for row in world.get("constitution_tables") or []:
        if isinstance(row, dict) and isinstance(row.get("entries"), list):
            constit_entries |= _array_keys(row["entries"], "system_constitution")
    index.register_many(RefKind.CONSTIT_TBL, constit_entries)

    index.register_many(RefKind.LIQUID, _liquid_material_keys(world.get("material_registry")))

    terrain_cats = index.keys(RefKind.TERRAIN_CAT)
    if not terrain_cats:
        terrain_cats = _inline_terrain_categories(world.get("terrain_registry")) | set(_DEFAULT_TERRAIN_CATEGORIES)
        index.register_many(RefKind.TERRAIN_CAT, terrain_cats)

    return index
