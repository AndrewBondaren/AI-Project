from dataclasses import dataclass

from app.db.mapper import bool_col, json_col, json_nullable_col


@dataclass
class World:
    __table__ = "worlds"
    __pk__    = "world_uid"

    world_uid:                  str
    name:                       str
    created_at:                 str
    narrative_language:         str  = "ru"
    measurement_system:         str  = "metric"
    current_tick:               int  = 0
    schema_version:             str | None = None
    world_map_version:          str | None = None

    # stat / skill / resist schemas
    stat_schema:                dict = json_col(default_factory=dict)
    skill_schema:               dict = json_col(default_factory=dict)
    resist_schema:              dict = json_col(default_factory=dict)
    derived_formulas:           dict = json_col(default_factory=dict)
    action_formulas:            dict = json_col(default_factory=dict)
    action_registry:            list = json_col(default_factory=list)

    # inventory
    slots:                      dict = json_col(default_factory=dict)
    weight_enabled:             bool = bool_col(default=True)
    volume_enabled:             bool = bool_col(default=True)
    overload_penalty_formula:   str | None = None

    # combat
    combat_settings:            dict = json_col(default_factory=dict)

    # hp / wounds
    hp_enabled:                 bool  = bool_col(default=True)
    faint_threshold:            float = 0.05
    faint_check_formula:        str | None = None
    wounds_enabled:             bool  = bool_col(default=False)
    wound_death_formula:        str | None = None
    wound_type_registry:        dict  = json_col(default_factory=dict)

    # calendar / time
    calendar:                   dict = json_col(default_factory=dict)
    sleep_penalty_formula:      str | None = None

    # registries
    colour_registry:            dict = json_col(default_factory=dict)
    texture_registry:           dict = json_col(default_factory=dict)
    lore_registry:              dict = json_col(default_factory=dict)
    tag_registry:               dict = json_col(default_factory=dict)
    intensity_level_registry:   dict = json_col(default_factory=dict)
    narrative_type_registry:    dict = json_col(default_factory=dict)
    body_schema_registry:       dict = json_col(default_factory=dict)
    muscle_tables:              dict = json_col(default_factory=dict)
    constitution_tables:        dict = json_col(default_factory=dict)
    npc_target_type_registry:   dict = json_col(default_factory=dict)
    npc_needs_registry:         dict = json_col(default_factory=dict)
    npc_goal_type_registry:     dict = json_col(default_factory=dict)
    character_trait_registry:   dict = json_col(default_factory=dict)
    respawn_type_registry:      dict = json_col(default_factory=dict)

    # location registries
    terrain_category_registry:      dict = json_col(default_factory=dict)
    terrain_registry:               list = json_col(default_factory=list)
    material_category_registry:     dict = json_col(default_factory=dict)
    material_use_type_registry:     dict = json_col(default_factory=dict)
    material_registry:              list = json_col(default_factory=list)
    cell_state_registry:            dict = json_col(default_factory=dict)
    danger_level_registry:          dict = json_col(default_factory=dict)
    road_type_registry:             dict = json_col(default_factory=dict)
    passage_type_registry:          dict = json_col(default_factory=dict)
    location_type_registry:         dict = json_col(default_factory=dict)
    location_state_registry:        dict = json_col(default_factory=dict)
    climate_zone_registry:          dict = json_col(default_factory=dict)
    weather_type_registry:          dict = json_col(default_factory=dict)
    resource_type_registry:         dict = json_col(default_factory=dict)
    city_size_registry:             list = json_col(default_factory=list)
    economic_tier_registry:         list = json_col(default_factory=list)
    building_template_registry:     dict = json_col(default_factory=dict)
    room_type_registry:             dict = json_col(default_factory=dict)
    barrier_template_registry:      dict = json_col(default_factory=dict)
    connection_type_registry:       list = json_col(default_factory=list)

    # generation policy (world template — tz_terrain_hydrology.md)
    hydrology:                      dict = json_col(default_factory=dict)
    caves:                          dict = json_col(default_factory=dict)

    # faction registries
    faction_relation_type_registry: dict = json_col(default_factory=dict)

    # world map settings
    season_temp_offsets:            dict = json_col(default_factory=dict)
    default_climate_zone:           str | None = None
    climate_temperature_peak_min:     int | None = None
    climate_temperature_peak_max:     int | None = None
    climate_pole_mode:              str | None = None   # manual | autoresolve
    climate_pole_preset:            str | None = None   # ice | desert | binary | …
    climate_local_influence_fraction: float | None = None  # × bbox diagonal for local override
    precipitation_liquid:           str | None = None   # ref → material_registry; fallback water
    climate_parallel_workers:       int | None = None   # cap CL-PAR pool; NULL = free_cores only
    z_max:                          int | None = None
    z_min:                          int | None = None
    map_subsurface_depth:           int = 20            # N_base skeleton band; min 10
    grid_bbox_padding:              int = 2             # anchor bbox ± cells (v1 extent)
    terrain_chunk_columns:          int = 32            # column-fill persist chunk side
    terrain_parallel_workers:       int | None = None   # cap TR-PAR pool; NULL = free_cores only
    world_bounds:                   dict | None = json_nullable_col(default=None)
    magma_band_thickness:           int | None = None   # 0/null = skip magma band
    closed_planet_grid:             bool = bool_col(default=False)
    elevation_lapse_rate:           float | None = None
    g:                              float = 1.0
    map_cell_size_m:                int = 3000  # world surface cell size in meters, multiples of 1000
    default_passage_height:         int = 2

    # custom field declarations
    player_fields:              dict = json_col(default_factory=dict)
    npc_fields:                 dict = json_col(default_factory=dict)

    # migration
    stat_conflict_mode:         str  = "soft"
    stat_migrations:            dict = json_col(default_factory=dict)
    registry_migrations:        dict = json_col(default_factory=dict)
    trait_change_log_threshold: float = 0.2
