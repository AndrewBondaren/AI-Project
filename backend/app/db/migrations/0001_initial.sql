PRAGMA auto_vacuum = INCREMENTAL;

-- ============================================================
-- worlds
-- ============================================================
CREATE TABLE IF NOT EXISTS worlds (
    world_uid                   TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    narrative_language          TEXT NOT NULL DEFAULT 'ru',
    measurement_system          TEXT NOT NULL DEFAULT 'metric',
    current_tick                INTEGER NOT NULL DEFAULT 0,
    schema_version              TEXT,
    world_map_version           TEXT,

    -- stat / skill / resist schemas
    stat_schema                 TEXT,
    skill_schema                TEXT,
    resist_schema               TEXT,
    derived_formulas            TEXT,
    action_formulas             TEXT,
    action_registry             TEXT,

    -- inventory
    slots                       TEXT,
    weight_enabled              INTEGER NOT NULL DEFAULT 1,
    volume_enabled              INTEGER NOT NULL DEFAULT 1,
    overload_penalty_formula    TEXT,

    -- combat
    combat_settings             TEXT,

    -- hp / wounds
    hp_enabled                  INTEGER NOT NULL DEFAULT 1,
    faint_threshold             REAL NOT NULL DEFAULT 0.05,
    faint_check_formula         TEXT,
    wounds_enabled              INTEGER NOT NULL DEFAULT 0,
    wound_death_formula         TEXT,
    wound_type_registry         TEXT,

    -- calendar / time
    calendar                    TEXT,
    sleep_penalty_formula       TEXT,

    -- registries (JSON arrays/objects)
    colour_registry             TEXT,
    texture_registry            TEXT,
    lore_registry               TEXT,
    tag_registry                TEXT,
    intensity_level_registry    TEXT,
    narrative_type_registry     TEXT,
    body_schema_registry        TEXT,
    muscle_tables               TEXT,
    constitution_tables         TEXT,
    npc_target_type_registry    TEXT,
    npc_needs_registry          TEXT,
    npc_goal_type_registry      TEXT,
    character_trait_registry    TEXT,
    respawn_type_registry       TEXT,

    -- location registries
    terrain_category_registry   TEXT,
    terrain_registry            TEXT,
    material_category_registry  TEXT,
    material_use_type_registry  TEXT,
    material_registry           TEXT,
    cell_state_registry         TEXT,
    danger_level_registry       TEXT,
    road_type_registry          TEXT,
    passage_type_registry       TEXT,
    location_type_registry      TEXT,
    location_state_registry     TEXT,
    climate_zone_registry       TEXT,
    weather_type_registry       TEXT,
    resource_type_registry      TEXT,
    city_size_registry          TEXT,
    economic_tier_registry      TEXT,
    building_template_registry  TEXT,
    room_type_registry          TEXT,
    barrier_template_registry   TEXT,
    connection_type_registry    TEXT,

    -- generation policy (hydrology / caves — tz_terrain_hydrology.md)
    hydrology                   TEXT,
    caves                       TEXT,

    -- faction registries
    faction_relation_type_registry TEXT,

    -- world map settings
    season_temp_offsets         TEXT,
    default_climate_zone        TEXT,
    climate_temperature_peak_min INTEGER,
    climate_temperature_peak_max INTEGER,
    climate_pole_mode           TEXT,
    climate_pole_preset         TEXT,
    climate_local_influence_fraction REAL,
    precipitation_liquid        TEXT,
    z_max                       INTEGER,
    z_min                       INTEGER,
    map_subsurface_depth        INTEGER NOT NULL DEFAULT 20,
    grid_bbox_padding           INTEGER NOT NULL DEFAULT 2,
    terrain_chunk_columns       INTEGER NOT NULL DEFAULT 32,
    world_bounds                TEXT,
    magma_band_thickness        INTEGER,
    closed_planet_grid          INTEGER NOT NULL DEFAULT 0,
    elevation_lapse_rate        REAL,
    g                           REAL NOT NULL DEFAULT 1.0,
    map_cell_size_m             INTEGER NOT NULL DEFAULT 3000,
    default_passage_height      INTEGER NOT NULL DEFAULT 2,

    -- custom fields declarations
    player_fields               TEXT,
    npc_fields                  TEXT,

    -- migration
    stat_conflict_mode          TEXT NOT NULL DEFAULT 'soft',
    stat_migrations             TEXT,
    registry_migrations         TEXT,
    trait_change_log_threshold  REAL NOT NULL DEFAULT 0.2,

    created_at                  TEXT NOT NULL
);

-- ============================================================
-- races
-- ============================================================
CREATE TABLE IF NOT EXISTS races (
    race_uid      TEXT PRIMARY KEY,
    world_uid      TEXT NOT NULL,
    display_race  TEXT NOT NULL,
    race_traits   TEXT,
    male          TEXT,
    female        TEXT,
    asexual       TEXT,
    both          TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- character_sheet  (players + NPCs, discriminator = character_type)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_sheet (
    character_uid           TEXT PRIMARY KEY,
    character_type          TEXT NOT NULL,    -- 'player' | 'npc'
    display_name            TEXT NOT NULL,

    -- identification
    system_class            TEXT,
    display_class           TEXT,
    system_gender           TEXT,
    display_gender          TEXT,
    system_race             TEXT,
    display_race            TEXT,
    system_nickname         TEXT,
    display_nickname        TEXT,
    system_reputation       TEXT,
    display_reputation      TEXT,
    system_social_status    TEXT,
    display_social_status   TEXT,
    system_age_type         TEXT,
    display_age_type        TEXT,
    system_title            TEXT,
    display_title           TEXT,

    -- location
    system_location         TEXT,
    display_location        TEXT,

    -- money (JSON map currency_id → amount, defined by world)
    system_money            TEXT,
    display_money           TEXT,

    -- vitals
    system_alive            INTEGER NOT NULL DEFAULT 1,
    system_conscious        INTEGER NOT NULL DEFAULT 1,
    system_barrier          TEXT,
    display_barrier         TEXT,

    -- stats (values map alias→value)
    system_stats            TEXT,
    display_stats           TEXT,

    -- narrative
    system_description      TEXT,
    display_description     TEXT,
    system_character        TEXT,
    display_character       TEXT,
    system_appearance       TEXT,
    display_appearance      TEXT,
    character_traits_dirty  INTEGER NOT NULL DEFAULT 0,
    system_birthday         TEXT,
    display_birthday        TEXT,
    system_origin           TEXT,
    display_origin          TEXT,
    system_motivation       TEXT,
    display_motivation      TEXT,
    system_background       TEXT,
    display_background      TEXT,

    -- faction (NPC only, nullable for players)
    system_faction_uid      TEXT,
    system_faction_rank     TEXT,
    display_faction_rank    TEXT,

    -- home / spawn / respawn
    system_home_location_uid    TEXT,
    system_home_settlement_uid  TEXT,
    work_location_uid           TEXT,
    spawn_location_uid          TEXT,
    can_respawn             INTEGER NOT NULL DEFAULT 0,
    respawn_after_ticks     INTEGER,
    system_respawn_place_type TEXT,
    respawn_location_uid    TEXT,

    -- interior position (interior локации)
    local_level_uid         TEXT REFERENCES location_levels(level_uid),
    local_x                 INTEGER,
    local_y                 INTEGER,

    -- NPC engine fields
    system_current_needs    TEXT,
    system_current_target   TEXT,
    system_npc_goal         TEXT,
    system_current_thoughts TEXT,
    display_current_thoughts TEXT,

    -- world binding
    world_uid                TEXT,
    world_schema_version    TEXT,

    created_at              TEXT NOT NULL,
    FOREIGN KEY (world_uid)                  REFERENCES worlds(world_uid),
    FOREIGN KEY (system_faction_uid)        REFERENCES factions(faction_uid),
    FOREIGN KEY (system_home_location_uid)  REFERENCES named_locations(location_uid),
    FOREIGN KEY (system_home_settlement_uid) REFERENCES named_locations(location_uid),
    FOREIGN KEY (work_location_uid)         REFERENCES named_locations(location_uid),
    FOREIGN KEY (spawn_location_uid)        REFERENCES named_locations(location_uid),
    FOREIGN KEY (respawn_location_uid)      REFERENCES named_locations(location_uid)
);

-- ============================================================
-- game_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS game_sessions (
    id                        TEXT PRIMARY KEY,
    world_uid                  TEXT NOT NULL,
    player_character_id       TEXT NOT NULL,
    restored_from_snapshot_id TEXT,
    created_at                TEXT NOT NULL,
    last_active_at            TEXT NOT NULL,
    UNIQUE (world_uid, player_character_id),
    FOREIGN KEY (world_uid)                REFERENCES worlds(world_uid),
    FOREIGN KEY (player_character_id)     REFERENCES character_sheet(character_uid),
    FOREIGN KEY (restored_from_snapshot_id) REFERENCES world_snapshots(snapshot_id)
);

-- ============================================================
-- scene_participants
-- ============================================================
CREATE TABLE IF NOT EXISTS scene_participants (
    session_id    TEXT NOT NULL,
    character_uid TEXT NOT NULL,
    PRIMARY KEY (session_id, character_uid),
    FOREIGN KEY (session_id)    REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (character_uid) REFERENCES character_sheet(character_uid)
);

-- ============================================================
-- turns  (один ход игрока — создаётся только при успехе)
-- ============================================================
CREATE TABLE IF NOT EXISTS turns (
    turn_id      TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    player_input TEXT NOT NULL,
    game_tick    INTEGER,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE
);

-- ============================================================
-- messages  (LLM-ответы в рамках хода)
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id   TEXT PRIMARY KEY,
    turn_id      TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'narrative',
    llm_output   TEXT,
    game_tick    INTEGER,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (turn_id)    REFERENCES turns(turn_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE
);

-- ============================================================
-- node_execution_logs  (логи нод — только при успехе)
-- ============================================================
CREATE TABLE IF NOT EXISTS node_execution_logs (
    log_id      TEXT PRIMARY KEY,
    turn_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    node_type   TEXT NOT NULL,
    node_input  TEXT,
    node_output TEXT,
    duration_ms INTEGER,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (turn_id)    REFERENCES turns(turn_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE
);

-- ============================================================
-- character_mastery  (skills per character)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_mastery (
    character_id  TEXT NOT NULL,
    system_skill  TEXT NOT NULL,
    value         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, system_skill),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_states  (status effects; one row per type)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_states (
    character_id  TEXT NOT NULL,
    type          TEXT NOT NULL,
    effects       TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    PRIMARY KEY (character_id, type),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_history
-- ============================================================
CREATE TABLE IF NOT EXISTS character_history (
    id                   TEXT PRIMARY KEY,
    character_id         TEXT NOT NULL,
    system_world_date    TEXT,
    display_world_date   TEXT,
    system_event_type    TEXT NOT NULL,
    display_event_type   TEXT NOT NULL,
    system_participants  TEXT,
    display_participants TEXT,
    system_description   TEXT NOT NULL,
    display_description  TEXT,
    is_narrated          INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_narrative_states
-- ============================================================
CREATE TABLE IF NOT EXISTS character_narrative_states (
    id                    TEXT PRIMARY KEY,
    character_id          TEXT NOT NULL,
    system_state          TEXT NOT NULL,
    display_state         TEXT NOT NULL,
    system_description    TEXT,
    display_description   TEXT,
    system_type           TEXT NOT NULL,
    display_type          TEXT NOT NULL,
    system_duration_type  TEXT NOT NULL,
    display_duration_type TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    created_at_tick       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_wounds
-- ============================================================
CREATE TABLE IF NOT EXISTS character_wounds (
    wound_uid          TEXT PRIMARY KEY,
    character_id       TEXT NOT NULL,
    body_part          TEXT NOT NULL,
    system_wound_type  TEXT NOT NULL,
    display_wound_type TEXT NOT NULL,
    severity           INTEGER NOT NULL,
    healing_state      TEXT NOT NULL DEFAULT 'fresh',
    effects            TEXT NOT NULL DEFAULT '[]',
    created_at         TEXT NOT NULL,
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- world_perks  (world perk registry)
-- ============================================================
CREATE TABLE IF NOT EXISTS world_perks (
    perk_uid            TEXT PRIMARY KEY,
    world_uid            TEXT NOT NULL,
    system_name         TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    system_description  TEXT,
    display_description TEXT,
    system_rank_value   TEXT,
    display_rank_value  TEXT,
    system_tags         TEXT,
    display_tags        TEXT,
    system_condition    TEXT,
    display_condition   TEXT,
    terrain_access      TEXT,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_perks  (common perks — uid ref + rank)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_perks (
    character_id  TEXT NOT NULL,
    perk_uid      TEXT NOT NULL,
    current_rank  TEXT,
    PRIMARY KEY (character_id, perk_uid),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE,
    FOREIGN KEY (perk_uid)     REFERENCES world_perks(perk_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_unique_perks  (AI-generated inline perks)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_unique_perks (
    character_id  TEXT NOT NULL,
    perk_uid      TEXT NOT NULL,
    snapshot      TEXT NOT NULL,
    PRIMARY KEY (character_id, perk_uid),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- character_inventory
-- ============================================================
CREATE TABLE IF NOT EXISTS character_inventory (
    character_id  TEXT NOT NULL,
    item_uid      TEXT NOT NULL,
    slot          TEXT NOT NULL,
    quantity      INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (character_id, item_uid, slot),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE,
    FOREIGN KEY (item_uid)     REFERENCES items(item_uid)
);

-- ============================================================
-- character_custom_fields  (NPC + player custom narrative fields)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_custom_fields (
    character_id   TEXT NOT NULL,
    system_field   TEXT NOT NULL,
    system_value   TEXT,
    display_value  TEXT,
    PRIMARY KEY (character_id, system_field),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- npc_thoughts_about  (persistent NPC memory of targets)
-- ============================================================
CREATE TABLE IF NOT EXISTS npc_thoughts_about (
    character_id      TEXT NOT NULL,
    target_uid        TEXT NOT NULL,
    system_thoughts   TEXT,
    display_thoughts  TEXT,
    updated_at        TEXT NOT NULL,
    PRIMARY KEY (character_id, target_uid),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
);

-- ============================================================
-- world_relations  (directed: source → target)
-- ============================================================
CREATE TABLE IF NOT EXISTS world_relations (
    world_uid       TEXT NOT NULL,
    source_uid     TEXT NOT NULL,
    target_uid     TEXT NOT NULL,
    relation_data  TEXT,
    PRIMARY KEY (world_uid, source_uid, target_uid),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- registry_dependencies  (fast lookup for registry key refs)
-- ============================================================
CREATE TABLE IF NOT EXISTS registry_dependencies (
    id            TEXT PRIMARY KEY,
    registry_type TEXT NOT NULL,
    registry_key  TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL
);

-- ============================================================
-- timelines + world_snapshots  (save / load / time travel)
-- ============================================================
CREATE TABLE IF NOT EXISTS timelines (
    timeline_id  TEXT PRIMARY KEY,
    world_uid     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

CREATE TABLE IF NOT EXISTS world_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    timeline_id        TEXT NOT NULL,
    world_uid           TEXT NOT NULL,
    turn_id            INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    parent_snapshot_id TEXT,
    snapshot_data      BLOB NOT NULL,
    snapshot_checksum  TEXT NOT NULL,
    FOREIGN KEY (timeline_id)        REFERENCES timelines(timeline_id),
    FOREIGN KEY (world_uid)           REFERENCES worlds(world_uid),
    FOREIGN KEY (parent_snapshot_id) REFERENCES world_snapshots(snapshot_id) ON DELETE RESTRICT
);

-- ============================================================
-- combat_state + combat_positions
-- ============================================================
CREATE TABLE IF NOT EXISTS combat_state (
    battle_uid       TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    location_uid     TEXT,
    round_number     INTEGER NOT NULL DEFAULT 1,
    round_seconds    INTEGER NOT NULL,
    started_at_tick  INTEGER NOT NULL,
    FOREIGN KEY (session_id)   REFERENCES game_sessions(id),
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid)
);

CREATE TABLE IF NOT EXISTS combat_positions (
    battle_uid    TEXT NOT NULL,
    character_uid TEXT NOT NULL,
    x             REAL NOT NULL,
    y             REAL NOT NULL,
    z             REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (battle_uid, character_uid),
    FOREIGN KEY (battle_uid)    REFERENCES combat_state(battle_uid) ON DELETE CASCADE,
    FOREIGN KEY (character_uid) REFERENCES character_sheet(character_uid)
);

-- ============================================================
-- items  (global registry)
-- ============================================================
CREATE TABLE IF NOT EXISTS items (
    item_uid    TEXT PRIMARY KEY,
    item_name   TEXT NOT NULL,
    item_type   TEXT NOT NULL,
    properties  TEXT,
    weight      INTEGER NOT NULL DEFAULT 0,
    volume      INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- world_items  (world-scoped item registry)
-- ============================================================
CREATE TABLE IF NOT EXISTS world_items (
    world_uid  TEXT NOT NULL,
    item_uid  TEXT NOT NULL,
    PRIMARY KEY (world_uid, item_uid),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid) ON DELETE CASCADE,
    FOREIGN KEY (item_uid) REFERENCES items(item_uid) ON DELETE CASCADE
);

-- ============================================================
-- factions
-- ============================================================
CREATE TABLE IF NOT EXISTS factions (
    faction_uid          TEXT PRIMARY KEY,
    world_uid             TEXT NOT NULL,
    display_name         TEXT NOT NULL,
    system_type          TEXT,
    display_type         TEXT,
    system_description   TEXT,
    display_description  TEXT,
    created_at           TEXT NOT NULL,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- faction_relations  (one row per pair; bidirectional lookup)
-- ============================================================
CREATE TABLE IF NOT EXISTS faction_relations (
    faction_a_uid   TEXT NOT NULL,
    faction_b_uid   TEXT NOT NULL,
    system_relation TEXT NOT NULL,
    trust           INTEGER NOT NULL DEFAULT 50,
    PRIMARY KEY (faction_a_uid, faction_b_uid),
    FOREIGN KEY (faction_a_uid) REFERENCES factions(faction_uid) ON DELETE CASCADE,
    FOREIGN KEY (faction_b_uid) REFERENCES factions(faction_uid) ON DELETE CASCADE
);

-- ============================================================
-- states
-- ============================================================
CREATE TABLE IF NOT EXISTS states (
    state_uid           TEXT PRIMARY KEY,
    world_uid           TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    government_type     TEXT,
    display_description TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

CREATE INDEX IF NOT EXISTS idx_states_world ON states (world_uid);

-- ============================================================
-- building_templates  (глобальная библиотека шаблонов зданий)
-- ============================================================
CREATE TABLE IF NOT EXISTS building_templates (
    template_uid   TEXT PRIMARY KEY,
    system_name    TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL,
    structure_type TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,
    source_file    TEXT
);

-- ============================================================
-- named_locations
-- ============================================================
CREATE TABLE IF NOT EXISTS named_locations (
    location_uid            TEXT PRIMARY KEY,
    world_uid                TEXT NOT NULL,
    parent_location_uid     TEXT,
    system_location_type    TEXT NOT NULL,
    system_location_subtype TEXT,
    display_name            TEXT NOT NULL,
    system_description      TEXT,
    display_description     TEXT,
    glossary_ref            TEXT,
    tag_refs                TEXT,
    is_discovered           INTEGER NOT NULL DEFAULT 0,
    is_accessible           INTEGER NOT NULL DEFAULT 1,
    entry_difficulty        INTEGER,
    guard_level             INTEGER,
    system_location_mood    TEXT,
    display_location_mood   TEXT,
    owner_uid               TEXT,
    system_climate_zone     TEXT,
    state_uid               TEXT,
    system_city_size        TEXT,
    system_economic_tier    TEXT,
    is_public               INTEGER NOT NULL DEFAULT 0,
    is_forbidden            INTEGER NOT NULL DEFAULT 0,
    is_selectable           INTEGER NOT NULL DEFAULT 1,
    map_x                   INTEGER,
    map_y                   INTEGER,
    map_z                   INTEGER,
    is_mobile               INTEGER NOT NULL DEFAULT 0,
    system_template_uid     TEXT,
    parent_wall_material    TEXT,
    parent_floor_material   TEXT,
    is_outdoor              INTEGER,
    is_sheltered            INTEGER NOT NULL DEFAULT 0,
    is_transit              INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    FOREIGN KEY (world_uid)            REFERENCES worlds(world_uid),
    FOREIGN KEY (parent_location_uid) REFERENCES named_locations(location_uid),
    FOREIGN KEY (owner_uid)           REFERENCES character_sheet(character_uid),
    FOREIGN KEY (system_template_uid) REFERENCES building_templates(template_uid)
);

-- ============================================================
-- map_cells
-- ============================================================
CREATE TABLE IF NOT EXISTS map_cells (
    world_uid                TEXT NOT NULL,
    x                       INTEGER NOT NULL,
    y                       INTEGER NOT NULL,
    z                       INTEGER NOT NULL,
    system_terrain                TEXT,
    system_building_element       TEXT,
    system_material               TEXT,
    is_structural                 INTEGER NOT NULL DEFAULT 0,
    travel_modifier_override      REAL,
    system_danger_level_override  TEXT,
    gap_width_override      INTEGER,
    temperature_base        INTEGER,
    rainfall                INTEGER,
    location_uid            TEXT,
    railing_sides           TEXT,
    system_facing           TEXT,
    display_facing          TEXT,
    glass_material          TEXT,
    hydrology               TEXT,
    PRIMARY KEY (world_uid, x, y, z),
    FOREIGN KEY (world_uid)    REFERENCES worlds(world_uid),
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid)
);

-- ============================================================
-- cell_states (состояния ячеек map_cells)
-- ============================================================
CREATE TABLE IF NOT EXISTS cell_states (
    id            TEXT PRIMARY KEY,
    world_uid      TEXT NOT NULL,
    x             INTEGER NOT NULL,
    y             INTEGER NOT NULL,
    z             INTEGER NOT NULL,
    system_state  TEXT NOT NULL,
    display_state TEXT NOT NULL,
    started_at    TEXT,
    ended_at      TEXT,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- location_levels (этажи / уровни локации)
-- ============================================================
CREATE TABLE IF NOT EXISTS location_levels (
    level_uid       TEXT PRIMARY KEY,
    location_uid    TEXT NOT NULL,
    z               INTEGER NOT NULL,
    z_height        INTEGER NOT NULL DEFAULT 3,
    display_name    TEXT NOT NULL,
    is_accessible   INTEGER NOT NULL DEFAULT 1,
    isolated        INTEGER NOT NULL DEFAULT 0,
    access_mechanic TEXT,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE
);

-- ============================================================
-- location_entry_points
-- ============================================================
CREATE TABLE IF NOT EXISTS location_entry_points (
    entry_uid                  TEXT PRIMARY KEY,
    location_uid               TEXT NOT NULL,
    x                          INTEGER NOT NULL,
    y                          INTEGER NOT NULL,
    z                          INTEGER NOT NULL,
    leads_to_level_uid         TEXT,
    display_name               TEXT NOT NULL,
    entry_difficulty_override  INTEGER,
    guard_level_override       INTEGER,
    is_discovered              INTEGER NOT NULL DEFAULT 0,
    is_accessible              INTEGER NOT NULL DEFAULT 1,
    glossary_ref               TEXT,
    tag_refs                   TEXT,
    FOREIGN KEY (location_uid)       REFERENCES named_locations(location_uid) ON DELETE CASCADE,
    FOREIGN KEY (leads_to_level_uid) REFERENCES location_levels(level_uid)
);

-- ============================================================
-- roads
-- ============================================================
CREATE TABLE IF NOT EXISTS roads (
    road_uid                 TEXT PRIMARY KEY,
    world_uid                 TEXT NOT NULL,
    display_name             TEXT,
    road_type                TEXT NOT NULL,
    travel_modifier_override REAL,
    from_location            TEXT NOT NULL,
    to_location              TEXT NOT NULL,
    is_bidirectional         INTEGER NOT NULL DEFAULT 1,
    danger_level             TEXT,
    glossary_ref             TEXT,
    tag_refs                 TEXT,
    FOREIGN KEY (world_uid)       REFERENCES worlds(world_uid),
    FOREIGN KEY (from_location)  REFERENCES named_locations(location_uid),
    FOREIGN KEY (to_location)    REFERENCES named_locations(location_uid)
);

-- ============================================================
-- location_passages (переходы между уровнями / комнатами)
-- ============================================================
CREATE TABLE IF NOT EXISTS location_passages (
    passage_uid         TEXT PRIMARY KEY,
    world_uid           TEXT NOT NULL,
    to_level_uid        TEXT NOT NULL,
    to_x                INTEGER NOT NULL,
    to_y                INTEGER NOT NULL,
    system_passage_type TEXT NOT NULL,
    from_level_uid      TEXT,        -- NULL = внешнее пространство (entry_point снаружи)
    from_x              INTEGER,
    from_y              INTEGER,
    is_bidirectional    INTEGER NOT NULL DEFAULT 1,
    display_name        TEXT,
    glossary_ref        TEXT,
    tag_refs            TEXT,
    FOREIGN KEY (world_uid)      REFERENCES worlds(world_uid),
    FOREIGN KEY (from_level_uid) REFERENCES location_levels(level_uid),
    FOREIGN KEY (to_level_uid)   REFERENCES location_levels(level_uid)
);

-- ============================================================
-- location_states
-- ============================================================
CREATE TABLE IF NOT EXISTS location_states (
    id                  TEXT PRIMARY KEY,
    location_uid        TEXT NOT NULL,
    level_uid           TEXT,
    system_state        TEXT NOT NULL,
    display_state       TEXT NOT NULL,
    system_description  TEXT,
    display_description TEXT,
    need_modifiers      TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE,
    FOREIGN KEY (level_uid)    REFERENCES location_levels(level_uid)
);

-- ============================================================
-- location_objects
-- ============================================================
CREATE TABLE IF NOT EXISTS location_objects (
    object_uid          TEXT PRIMARY KEY,
    level_uid           TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    x                   INTEGER NOT NULL,
    y                   INTEGER NOT NULL,
    placement_type      TEXT NOT NULL,
    wall_direction      TEXT,
    height_offset       INTEGER,
    parent_object_uid   TEXT,
    display_as_group    INTEGER NOT NULL DEFAULT 0,
    system_description  TEXT,
    display_description TEXT,
    is_interactive      INTEGER NOT NULL DEFAULT 0,
    is_takeable         INTEGER NOT NULL DEFAULT 1,
    item_uid            TEXT,
    is_accessible       INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (level_uid)          REFERENCES location_levels(level_uid) ON DELETE CASCADE,
    FOREIGN KEY (parent_object_uid)  REFERENCES location_objects(object_uid),
    FOREIGN KEY (item_uid)           REFERENCES items(item_uid)
);

-- ============================================================
-- location_weather
-- ============================================================
CREATE TABLE IF NOT EXISTS location_weather (
    location_uid    TEXT PRIMARY KEY,
    system_weather  TEXT NOT NULL,
    intensity       INTEGER NOT NULL DEFAULT 50,
    remaining_ticks INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE
);

-- ============================================================
-- location_resources
-- ============================================================
CREATE TABLE IF NOT EXISTS location_resources (
    id              TEXT PRIMARY KEY,
    location_uid    TEXT NOT NULL,
    level_uid       TEXT,
    system_resource TEXT NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 0,
    max_quantity    INTEGER NOT NULL,
    regen_override  INTEGER,
    is_discovered   INTEGER NOT NULL DEFAULT 0,
    is_accessible   INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE,
    FOREIGN KEY (level_uid)    REFERENCES location_levels(level_uid)
);

-- ============================================================
-- location_faction_influence
-- ============================================================
CREATE TABLE IF NOT EXISTS location_faction_influence (
    id           TEXT PRIMARY KEY,
    location_uid TEXT NOT NULL,
    faction_uid  TEXT NOT NULL,
    influence    INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE,
    FOREIGN KEY (faction_uid)  REFERENCES factions(faction_uid) ON DELETE CASCADE
);

-- ============================================================
-- location_faction_access
-- ============================================================
CREATE TABLE IF NOT EXISTS location_faction_access (
    location_uid TEXT NOT NULL,
    faction_uid  TEXT NOT NULL,
    is_allowed   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (location_uid, faction_uid),
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid) ON DELETE CASCADE,
    FOREIGN KEY (faction_uid)  REFERENCES factions(faction_uid) ON DELETE CASCADE
);

-- ============================================================
-- world_history
-- ============================================================
CREATE TABLE IF NOT EXISTS world_history (
    id                   TEXT PRIMARY KEY,
    world_uid             TEXT NOT NULL,
    location_uid         TEXT,
    system_world_date    TEXT,
    display_world_date   TEXT,
    system_event_type    TEXT NOT NULL,
    display_event_type   TEXT NOT NULL,
    system_description   TEXT NOT NULL,
    display_description  TEXT,
    created_at           TEXT NOT NULL,
    FOREIGN KEY (world_uid)    REFERENCES worlds(world_uid),
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid)
);

-- ============================================================
-- social_status
-- ============================================================
CREATE TABLE IF NOT EXISTS social_status (
    system_social_status  TEXT PRIMARY KEY,
    display_social_status TEXT NOT NULL,
    social_status_weight  INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- age_type
-- ============================================================
CREATE TABLE IF NOT EXISTS age_type (
    system_age_type  TEXT PRIMARY KEY,
    display_age_type TEXT NOT NULL
);

-- ============================================================
-- appearance lookup tables
-- ============================================================
CREATE TABLE IF NOT EXISTS hair_type (
    system_hair_type  TEXT PRIMARY KEY,
    display_hair_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hair_shape (
    system_hair_shape       TEXT PRIMARY KEY,
    display_hair_shape      TEXT NOT NULL,
    system_hair_shape_is_auto INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skin_type (
    system_skin_type  TEXT PRIMARY KEY,
    display_skin_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brows_type (
    system_brows_type  TEXT PRIMARY KEY,
    display_brows_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brows_shape (
    system_brows_shape  TEXT PRIMARY KEY,
    display_brows_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beard_type (
    system_beard_type  TEXT PRIMARY KEY,
    display_beard_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beard_shape (
    system_beard_shape        TEXT PRIMARY KEY,
    display_beard_shape       TEXT NOT NULL,
    system_beard_shape_is_auto INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS eye_type (
    system_eye_type        TEXT PRIMARY KEY,
    display_eye_type       TEXT NOT NULL,
    system_eye_type_weight INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS eye_placement (
    system_eye_placement  TEXT PRIMARY KEY,
    display_eye_placement TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eye_iris_type (
    system_eye_iris_type  TEXT PRIMARY KEY,
    display_eye_iris_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eye_lid_type (
    system_eye_lid_type  TEXT PRIMARY KEY,
    display_eye_lid_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eye_pupil_type (
    system_eye_pupil_type  TEXT PRIMARY KEY,
    display_eye_pupil_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eye_roundness (
    system_eye_roundness        TEXT PRIMARY KEY,
    display_eye_roundness       TEXT NOT NULL,
    system_eye_roundness_weight INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mouth_type (
    system_mouth_type  TEXT PRIMARY KEY,
    display_mouth_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lip_shape (
    system_lip_shape  TEXT PRIMARY KEY,
    display_lip_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teeth_type (
    system_teeth_type  TEXT PRIMARY KEY,
    display_teeth_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jaw_shape (
    system_jaw_shape  TEXT PRIMARY KEY,
    display_jaw_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nose_type (
    system_nose_type  TEXT PRIMARY KEY,
    display_nose_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nose_shape (
    system_nose_shape  TEXT PRIMARY KEY,
    display_nose_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ear_type (
    system_ear_type  TEXT PRIMARY KEY,
    display_ear_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ear_shape (
    system_ear_shape  TEXT PRIMARY KEY,
    display_ear_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS breast_type (
    system_breast_type  TEXT PRIMARY KEY,
    display_breast_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS breast_shape (
    system_breast_shape  TEXT PRIMARY KEY,
    display_breast_shape TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genitals_type (
    system_genitals_type  TEXT PRIMARY KEY,
    display_genitals_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_pitch (
    system_voice_pitch  TEXT PRIMARY KEY,
    display_voice_pitch TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_timbre (
    system_voice_timbre  TEXT PRIMARY KEY,
    display_voice_timbre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS body_hair_density (
    system_body_hair_density TEXT PRIMARY KEY,
    display_body_hair_density TEXT NOT NULL,
    system_body_hair_weight   INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- session_scene  (текущее состояние сцены на сессию)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_scene (
    session_id   TEXT PRIMARY KEY,
    location_uid TEXT,
    level_uid    TEXT,
    description  TEXT NOT NULL,
    actors       TEXT NOT NULL DEFAULT '[]',
    updated_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (session_id)   REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid),
    FOREIGN KEY (level_uid)    REFERENCES location_levels(level_uid)
);

-- ============================================================
-- session_pending  (Outbox pattern: pending input + snapshot)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_pending (
    session_id   TEXT PRIMARY KEY,
    player_input TEXT NOT NULL,
    snapshot     TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE
);

-- ============================================================
-- connection_nodes
-- ============================================================
CREATE TABLE IF NOT EXISTS connection_nodes (
    node_uid        TEXT PRIMARY KEY,
    x               INTEGER NOT NULL,
    y               INTEGER NOT NULL,
    z               INTEGER NOT NULL,
    node_type       TEXT NOT NULL,   -- "intersection"|"settlement_gate"|"portal"|"building_entrance"|"location_hub"|"waypoint"
    graph_level     TEXT NOT NULL,   -- "world"|"city"|"district"|"area"
    world_uid       TEXT NOT NULL REFERENCES worlds(world_uid),
    location_uid    TEXT REFERENCES named_locations(location_uid),

    -- только для node_type="portal"
    portal_type                      TEXT,
    portal_destinations              TEXT,        -- JSON: list[dict]
    portal_bidirectional             INTEGER,     -- 0|1|null
    portal_is_active                 INTEGER,     -- 0|1|null
    portal_blocked_behavior_override TEXT
);

-- ============================================================
-- connection_edges
-- ============================================================
CREATE TABLE IF NOT EXISTS connection_edges (
    edge_uid            TEXT PRIMARY KEY,
    from_node_uid       TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    to_node_uid         TEXT NOT NULL REFERENCES connection_nodes(node_uid),
    connection_type     TEXT NOT NULL,
    graph_level         TEXT NOT NULL,
    world_uid           TEXT NOT NULL REFERENCES worlds(world_uid),

    bidirectional       INTEGER NOT NULL DEFAULT 1,
    lanes_per_side      INTEGER NOT NULL DEFAULT 1,
    width_cells         INTEGER,
    bridge_subtype      TEXT,
    parent_edge_uid     TEXT REFERENCES connection_edges(edge_uid),
    side                TEXT,                -- "left"|"right"; только для sidewalk
    material            TEXT,
    condition           INTEGER NOT NULL DEFAULT 100,
    features            TEXT,                -- JSON: list[string]
    lighting_type       TEXT,
    danger_level        TEXT NOT NULL DEFAULT 'none',
    has_sidewalk        INTEGER NOT NULL DEFAULT 0,
    under_construction  INTEGER NOT NULL DEFAULT 0,
    under_repair        INTEGER NOT NULL DEFAULT 0,
    street_objects      TEXT,                -- JSON: list[dict]
    traversal_conditions TEXT               -- JSON: dict
);

-- ============================================================
-- connection_edge_cells
-- ============================================================
CREATE TABLE IF NOT EXISTS connection_edge_cells (
    edge_uid    TEXT NOT NULL REFERENCES connection_edges(edge_uid) ON DELETE CASCADE,
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    z           INTEGER NOT NULL,
    seq         INTEGER NOT NULL,   -- порядок ячеек вдоль ребра
    PRIMARY KEY (edge_uid, x, y, z)
);

-- ============================================================
-- indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_character_sheet_world    ON character_sheet (world_uid);
CREATE INDEX IF NOT EXISTS idx_character_sheet_location ON character_sheet (system_location);
CREATE INDEX IF NOT EXISTS idx_character_sheet_type     ON character_sheet (character_type);

CREATE INDEX IF NOT EXISTS idx_turns_session            ON turns    (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_turn            ON messages (turn_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_session         ON messages (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_node_logs_turn           ON node_execution_logs (turn_id, created_at);

CREATE INDEX IF NOT EXISTS idx_game_sessions_world      ON game_sessions (world_uid);

CREATE INDEX IF NOT EXISTS idx_character_history_char   ON character_history (character_id);
CREATE INDEX IF NOT EXISTS idx_character_wounds_char    ON character_wounds (character_id);
CREATE INDEX IF NOT EXISTS idx_npc_thoughts_char        ON npc_thoughts_about (character_id);

CREATE INDEX IF NOT EXISTS idx_world_relations_source   ON world_relations (world_uid, source_uid);
CREATE INDEX IF NOT EXISTS idx_world_relations_target   ON world_relations (world_uid, target_uid);

CREATE INDEX IF NOT EXISTS idx_registry_deps_lookup     ON registry_dependencies (registry_type, registry_key);
CREATE INDEX IF NOT EXISTS idx_registry_deps_entity     ON registry_dependencies (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_timeline       ON world_snapshots (timeline_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_parent         ON world_snapshots (parent_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_races_world              ON races (world_uid);

CREATE INDEX IF NOT EXISTS idx_world_perks_world         ON world_perks (world_uid);

CREATE INDEX IF NOT EXISTS idx_factions_world           ON factions (world_uid);

CREATE INDEX IF NOT EXISTS idx_named_locations_world    ON named_locations (world_uid);
CREATE INDEX IF NOT EXISTS idx_named_locations_parent   ON named_locations (parent_location_uid);
CREATE INDEX IF NOT EXISTS idx_named_locations_type     ON named_locations (world_uid, system_location_type);
CREATE INDEX IF NOT EXISTS idx_named_locations_public   ON named_locations (world_uid, is_public);

CREATE INDEX IF NOT EXISTS idx_map_cells_location_z     ON map_cells (world_uid, location_uid, z);

CREATE INDEX IF NOT EXISTS idx_location_levels_location ON location_levels (location_uid);
CREATE INDEX IF NOT EXISTS idx_location_passages_from   ON location_passages (from_level_uid);
CREATE INDEX IF NOT EXISTS idx_location_passages_to     ON location_passages (to_level_uid);

CREATE INDEX IF NOT EXISTS idx_map_cells_location       ON map_cells (world_uid, location_uid, z);
CREATE INDEX IF NOT EXISTS idx_map_cells_xy             ON map_cells (world_uid, x, y);

CREATE INDEX IF NOT EXISTS idx_cell_states_cell         ON cell_states (world_uid, x, y, z);
CREATE INDEX IF NOT EXISTS idx_cell_states_active       ON cell_states (world_uid, x, y, z) WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_roads_world              ON roads (world_uid);
CREATE INDEX IF NOT EXISTS idx_roads_from               ON roads (from_location);
CREATE INDEX IF NOT EXISTS idx_roads_to                 ON roads (to_location);

CREATE INDEX IF NOT EXISTS idx_location_states_loc      ON location_states (location_uid);
CREATE INDEX IF NOT EXISTS idx_location_objects_level   ON location_objects (level_uid);
CREATE INDEX IF NOT EXISTS idx_location_resources_loc   ON location_resources (location_uid);
CREATE INDEX IF NOT EXISTS idx_location_faction_inf_loc ON location_faction_influence (location_uid);

CREATE INDEX IF NOT EXISTS idx_world_history_world      ON world_history (world_uid);
CREATE INDEX IF NOT EXISTS idx_world_history_location   ON world_history (location_uid);

CREATE INDEX IF NOT EXISTS idx_conn_nodes_world         ON connection_nodes (world_uid);
CREATE INDEX IF NOT EXISTS idx_conn_nodes_location      ON connection_nodes (world_uid, location_uid);
CREATE INDEX IF NOT EXISTS idx_conn_nodes_level         ON connection_nodes (world_uid, graph_level);

CREATE INDEX IF NOT EXISTS idx_conn_edges_world         ON connection_edges (world_uid);
CREATE INDEX IF NOT EXISTS idx_conn_edges_from          ON connection_edges (from_node_uid);
CREATE INDEX IF NOT EXISTS idx_conn_edges_to            ON connection_edges (to_node_uid);
CREATE INDEX IF NOT EXISTS idx_conn_edges_level         ON connection_edges (world_uid, graph_level);

CREATE INDEX IF NOT EXISTS idx_conn_edge_cells_edge     ON connection_edge_cells (edge_uid);
