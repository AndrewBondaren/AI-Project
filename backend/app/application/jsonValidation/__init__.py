"""JSON import validation + normalize — single home for wire → dataModel.

Contract: ``docs/tz_json_validation.md``.

Layers:
  ``resolve``   — per-field ``WireFieldPolicy`` (Strict / Default / Ignore)
  ``facade``    — import / CRUD normalize (strict → 422)
  ``worldRow``  — ``worlds`` DB row → typed POJOs (runtime reads)
  ``index``     — REF-W cross-refs after normalize (import only)
  ``wire``      — ENUM-E wire parse
"""

from app.application.jsonValidation.bundle import normalize_bundle_connections
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.index import (
    RefKind,
    WorldRegistryIndex,
    build_world_registry_index,
    validate_ref_w,
)
from app.application.jsonValidation.resolve import (
    StrictFieldError,
    resolve_model,
    resolve_root_dict,
    resolve_root_list,
)
from app.application.jsonValidation.types import (
    FieldPathError,
    ImportValidationError,
    import_validation_http_detail,
)
from app.application.jsonValidation.wire import WireEnumError, parse_enum
from app.application.jsonValidation.worldRow import (
    barrier_template_defaults,
    barrier_templates,
    building_layout_templates,
    building_template_registry,
    city_sizes,
    climate_scalars,
    climate_zones,
    connection_types,
    default_precipitation_liquid,
    district_templates,
    economic_tier_engine,
    economic_tier_rows,
    economic_tiers,
    hydrology,
    hydrology_dict,
    legacy_standalone_water_material,
    location_moods,
    location_types,
    lore,
    material_rows,
    materials,
    materials_engine,
    road_settings,
    road_settings_rows,
    river_type_classify_defaults,
    room_types,
    terrain,
    terrain_categories,
    terrain_masks,
    terrain_masks_dict,
    terrain_rows,
    terrain_scalars,
    terrain_system_keys,
    weather_types,
)
from app.application.jsonValidation.worldSlices import (
    WORLD_SLICES,
    WorldSlice,
    climate_zone_wire_from_raw,
    facade_world_slices,
    merge_facade_slices,
    merge_world_slice,
    slice_for_world_key,
)

__all__ = [
    "FieldPathError",
    "ImportValidationError",
    "StrictFieldError",
    "WireEnumError",
    "RefKind",
    "WORLD_SLICES",
    "WorldRegistryIndex",
    "WorldSlice",
    "barrier_template_defaults",
    "barrier_templates",
    "building_layout_templates",
    "building_template_registry",
    "build_world_registry_index",
    "city_sizes",
    "climate_scalars",
    "climate_zone_wire_from_raw",
    "climate_zones",
    "connection_types",
    "default_precipitation_liquid",
    "district_templates",
    "economic_tier_engine",
    "economic_tier_rows",
    "economic_tiers",
    "facade_world_slices",
    "hydrology",
    "hydrology_dict",
    "legacy_standalone_water_material",
    "location_moods",
    "location_types",
    "lore",
    "import_validation_http_detail",
    "material_rows",
    "materials",
    "materials_engine",
    "merge_facade_slices",
    "merge_world_slice",
    "normalize_bundle_connections",
    "normalize_world",
    "parse_enum",
    "resolve_model",
    "resolve_root_dict",
    "resolve_root_list",
    "road_settings",
    "road_settings_rows",
    "river_type_classify_defaults",
    "room_types",
    "slice_for_world_key",
    "validate_ref_w",
    "terrain",
    "terrain_categories",
    "terrain_masks",
    "terrain_masks_dict",
    "terrain_rows",
    "terrain_scalars",
    "terrain_system_keys",
    "weather_types",
]
