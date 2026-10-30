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
    transition_type_registry    TEXT,
    location_type_registry      TEXT,
    settlement_specialization_registry TEXT,
    location_state_registry     TEXT,
    climate_zone_registry       TEXT,
    weather_type_registry       TEXT,
    resource_type_registry      TEXT,
    crops_registry              TEXT,
    livestock_registry          TEXT,
    city_size_registry          TEXT,
    district_zone_preference    TEXT,
    economic_tier_registry      TEXT,
    purpose_packs               TEXT,  -- enabled pack ids; omit/[] → [base, fantasy]
    purpose_pack_registry       TEXT,  -- pack recipes (canonical ⊕ overlay); base frozen
    room_type_registry          TEXT,
    barrier_template_registry   TEXT,
    connection_type_registry    TEXT,
    canal_template_registry     TEXT,  -- R36q canal bodies (system_type + earthen/structure)
    relief_pick_policy          TEXT,
    relief_grade_obstacle_policy TEXT,  -- truncate_skip | allow_flush (R36n); NULL → POJO default
    race_template_registry      TEXT,
    perk_template_registry      TEXT,
    library_pins                TEXT,  -- pin-набор мира: пары library_kind/local_uid (tz_template_library_packs §1.1)

    -- generation policy (hydrology / caves / terrain masks — tz_terrain_hydrology.md, tz_map_light_bake.md)
    hydrology                   TEXT,
    terrain_masks               TEXT,
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
    climate_parallel_workers    INTEGER,
    z_max                       INTEGER,
    z_min                       INTEGER,
    map_subsurface_depth        INTEGER NOT NULL DEFAULT 0,
    grid_bbox_padding           INTEGER NOT NULL DEFAULT 2,
    terrain_chunk_columns       INTEGER NOT NULL DEFAULT 32,
    terrain_parallel_workers    INTEGER,
    world_bounds                TEXT,
    world_topology_mode         TEXT NOT NULL DEFAULT 'wrapped',
    magma_band_thickness        INTEGER,
    closed_planet_grid          INTEGER NOT NULL DEFAULT 0,
    elevation_lapse_rate        REAL,
    g                           REAL NOT NULL DEFAULT 1.0,
    fine_cells_per_map_cell     INTEGER NOT NULL DEFAULT 1000,
    default_passage_height      INTEGER NOT NULL DEFAULT 2,

    -- custom fields declarations
    player_fields               TEXT,
    npc_fields                  TEXT,

    -- migration
    stat_conflict_mode          TEXT NOT NULL DEFAULT 'soft',
    stat_migrations             TEXT,
    registry_migrations         TEXT,
    trait_change_log_threshold  REAL NOT NULL DEFAULT 0.2,

    -- world pack (TR-PACK)
    terrain_pack_path           TEXT,
    terrain_pack_hash           TEXT,
    terrain_pack_version        TEXT,
    world_map_cells_per_tile    INTEGER,

    created_at                  TEXT NOT NULL
);

-- ============================================================
-- race_templates  (global library — tz_world_bundle WB-13)
-- ============================================================
CREATE TABLE IF NOT EXISTS race_templates (
    template_uid  TEXT PRIMARY KEY,
    system_name   TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    race_traits   TEXT,
    male          TEXT,
    female        TEXT,
    asexual       TEXT,
    both          TEXT,
    created_at    TEXT NOT NULL
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
-- perk_templates  (global library — tz_world_bundle WB-14)
-- ============================================================
CREATE TABLE IF NOT EXISTS perk_templates (
    template_uid        TEXT PRIMARY KEY,
    system_name         TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    system_description  TEXT,
    display_description TEXT,
    system_rank_value   TEXT,
    display_rank_value  TEXT,
    system_tags         TEXT,
    display_tags        TEXT,
    system_condition    TEXT,
    display_condition   TEXT,
    terrain_access      TEXT
);

-- ============================================================
-- character_perks  (common perks — uid ref + rank → global library)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_perks (
    character_id  TEXT NOT NULL,
    perk_uid      TEXT NOT NULL,
    current_rank  TEXT,
    PRIMARY KEY (character_id, perk_uid),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE,
    FOREIGN KEY (perk_uid)     REFERENCES perk_templates(template_uid) ON DELETE CASCADE
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
    UNIQUE (world_uid, timeline_id),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

CREATE TABLE IF NOT EXISTS world_snapshots (
    snapshot_id TEXT NOT NULL PRIMARY KEY CHECK (snapshot_id IS NULL OR (length(snapshot_id) > 0)),
    timeline_id TEXT NOT NULL CHECK (timeline_id IS NULL OR (length(timeline_id) > 0)),
    world_uid TEXT NOT NULL CHECK (world_uid IS NULL OR (length(world_uid) > 0)),
    turn_id INTEGER NOT NULL CHECK (turn_id IS NULL OR (typeof(turn_id) = 'integer' AND turn_id >= 1)),
    created_at TEXT NOT NULL CHECK (created_at IS NULL OR (length(created_at) > 0)),
    parent_snapshot_id TEXT CHECK (parent_snapshot_id IS NULL OR (length(parent_snapshot_id) > 0)),
    snapshot_data BLOB NOT NULL CHECK (typeof(snapshot_data) = 'blob' AND length(snapshot_data) > 0),
    snapshot_checksum TEXT NOT NULL CHECK (snapshot_checksum IS NULL OR (length(snapshot_checksum) = 64 AND snapshot_checksum NOT GLOB '*[^0-9a-f]*')),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    envelope_format_version INTEGER NOT NULL CHECK (envelope_format_version IS NULL OR (typeof(envelope_format_version) = 'integer' AND envelope_format_version >= 1)),
    base_pack_hash TEXT NOT NULL CHECK (base_pack_hash IS NULL OR (length(base_pack_hash) = 64 AND base_pack_hash NOT GLOB '*[^0-9a-f]*')),
    UNIQUE (world_uid, snapshot_id),
    UNIQUE (world_uid, timeline_id, operation_id),
    UNIQUE (operation_id),
    UNIQUE (timeline_id, turn_id),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid),
    FOREIGN KEY (world_uid, timeline_id) REFERENCES timelines(world_uid, timeline_id),
    FOREIGN KEY (world_uid, parent_snapshot_id) REFERENCES world_snapshots(world_uid, snapshot_id) ON DELETE RESTRICT,
    FOREIGN KEY (world_uid, operation_id) REFERENCES publication_operations(world_uid, operation_id)
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
-- plot_templates (шаблоны участков; owner/membership — library pack catalog)
-- ============================================================
CREATE TABLE IF NOT EXISTS plot_templates (
    template_uid TEXT PRIMARY KEY,
    system_name  TEXT NOT NULL,  -- readable key, not member identity or UNIQUE
    display_name TEXT NOT NULL,
    data         TEXT NOT NULL,
    source_file  TEXT
);

-- ============================================================
-- building_templates  (глобальная библиотека шаблонов зданий)
-- ============================================================
CREATE TABLE IF NOT EXISTS building_templates (
    template_uid   TEXT PRIMARY KEY,
    system_name    TEXT NOT NULL,  -- не глобально UNIQUE (tz_template_library_packs §3): локальный ключ, уникальность — в library_pack_members
    display_name   TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,
    source_file    TEXT
);

-- ============================================================
-- relief_templates  (глобальная библиотека шаблонов relief grade)
-- ============================================================
CREATE TABLE IF NOT EXISTS relief_templates (
    template_uid   TEXT PRIMARY KEY,
    system_name    TEXT NOT NULL,  -- не глобально UNIQUE (tz_template_library_packs §3): локальный ключ, уникальность — в library_pack_members
    display_name   TEXT NOT NULL,
    context        TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,
    source_file    TEXT
);

-- ============================================================
-- structure_templates  (глобальная библиотека геометрии интерьеров, 5o)
-- template_uid == StructureTemplate.system_name (uuid из JSON, не uuid5)
-- ============================================================
CREATE TABLE IF NOT EXISTS structure_templates (
    template_uid   TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,
    source_file    TEXT
);

-- ============================================================
-- library_packs  (каталог паков библиотек — tz_template_library_packs §3)
-- Ровно один владелец: owner_world_uid NULL = библиотека движка,
-- NOT NULL = библиотека мира (mutable, каскадно умирает с миром).
-- source_pack_uid — provenance remap-операции, не enforced FK: удаление
-- engine-пака безопасно всегда (миры держат инстансы-копии); dangling
-- значение читается как статус «source deleted». Таблицы bindings нет —
-- доступность = owner_world_uid либо default-статус.
-- ============================================================
CREATE TABLE IF NOT EXISTS library_packs (
    pack_uid         TEXT PRIMARY KEY,
    system_name      TEXT NOT NULL UNIQUE,
    pack_name        TEXT NOT NULL,
    display_name     TEXT NOT NULL,
    version          TEXT NOT NULL DEFAULT '1.0',
    owner_world_uid  TEXT REFERENCES worlds(world_uid) ON DELETE CASCADE,
    source_pack_uid  TEXT              -- provenance: пак-источник; может ссылаться на удалённый пак
);

-- ============================================================
-- library_pack_members  (состав паков; тела — в доменных таблицах)
-- Одна строка = единственный владелец члена. source_template_uid —
-- provenance remap-операции, не FK-integrity (ТЗ §3): источник может
-- быть удалён, dangling допустим как у required_pack_uid.
-- ============================================================
CREATE TABLE IF NOT EXISTS library_pack_members (
    template_uid        TEXT PRIMARY KEY,
    pack_uid            TEXT NOT NULL REFERENCES library_packs(pack_uid) ON DELETE CASCADE,
    library_kind        TEXT NOT NULL,
    local_uid           TEXT NOT NULL,
    source_template_uid TEXT,          -- provenance: член-источник; может ссылаться на удалённого члена
    creation_kind       TEXT NOT NULL DEFAULT 'authored'
                        CHECK (creation_kind IN ('authored', 'pack_copy', 'member_copy'))
);

-- ============================================================
-- library_pack_dependencies  (явные зависимости паков)
-- required_pack_uid не FK: допускает ещё не импортированный пак —
-- неполнота диагностируется, не блокируется (ТЗ §3, §5).
-- ============================================================
CREATE TABLE IF NOT EXISTS library_pack_dependencies (
    pack_uid          TEXT NOT NULL REFERENCES library_packs(pack_uid) ON DELETE CASCADE,
    required_pack_uid TEXT NOT NULL,
    PRIMARY KEY (pack_uid, required_pack_uid)
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
    system_economic_tier    TEXT,
    is_public               INTEGER NOT NULL DEFAULT 0,
    is_forbidden            INTEGER NOT NULL DEFAULT 0,
    is_selectable           INTEGER NOT NULL DEFAULT 1,
    map_x                   INTEGER,
    map_y                   INTEGER,
    map_z                   INTEGER,
    is_mobile               INTEGER NOT NULL DEFAULT 0,
    system_template_uid     TEXT,              -- applied library member uid (plot for city buildings)
    system_structure_template_uid TEXT,        -- structure member uid actually materialized (B4)
    parent_wall_material    TEXT,
    parent_floor_material   TEXT,
    is_outdoor              INTEGER,
    is_sheltered            INTEGER NOT NULL DEFAULT 0,
    is_transit              INTEGER NOT NULL DEFAULT 0,
    location_payload        TEXT,              -- typed payload JSON; contract via location_type_registry[].payload_kind
    created_at              TEXT NOT NULL,
    FOREIGN KEY (world_uid)            REFERENCES worlds(world_uid),
    FOREIGN KEY (parent_location_uid) REFERENCES named_locations(location_uid),
    FOREIGN KEY (owner_uid)           REFERENCES character_sheet(character_uid),
    -- Template refs point at the shared member catalog; a member removed via
    -- the explicit used-delete override clears the persisted ref to NULL.
    FOREIGN KEY (system_template_uid) REFERENCES library_pack_members(template_uid) ON DELETE SET NULL,
    FOREIGN KEY (system_structure_template_uid) REFERENCES library_pack_members(template_uid) ON DELETE SET NULL
);

-- ============================================================
-- map_cell_patches (gameplay deltas over World Pack)
-- ============================================================
CREATE TABLE IF NOT EXISTS map_cell_patches (
    world_uid                TEXT NOT NULL,
    x                       INTEGER NOT NULL,
    y                       INTEGER NOT NULL,
    z                       INTEGER NOT NULL,
    layer_kind              TEXT NOT NULL DEFAULT 'structure',
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
    system_grade_uid        TEXT,              -- R36j; omit/NULL if not in grade (no FK: L0 SoT = pack)
    PRIMARY KEY (world_uid, x, y, z),
    FOREIGN KEY (world_uid)    REFERENCES worlds(world_uid),
    FOREIGN KEY (location_uid) REFERENCES named_locations(location_uid)
);

-- ============================================================
-- region_states (entity store; StateChangeConsumer is the sole state writer)
-- ============================================================
CREATE TABLE IF NOT EXISTS region_states (
    world_uid               TEXT NOT NULL,
    region_uid              TEXT NOT NULL,
    current_type            TEXT NOT NULL,
    pending_target          TEXT,
    progress                REAL NOT NULL DEFAULT 0,
    last_eval_tick          INTEGER NOT NULL DEFAULT 0,
    overrides               TEXT NOT NULL DEFAULT '{}',
    history                 TEXT NOT NULL DEFAULT '[]',
    spec_fingerprint       TEXT,
    tombstone               INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    PRIMARY KEY (world_uid, region_uid),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- chunk_refine_jobs (L2 background refine queue state)
-- ============================================================
CREATE TABLE IF NOT EXISTS chunk_refine_jobs (
    job_uid                 TEXT PRIMARY KEY,
    world_uid               TEXT NOT NULL,
    gx                      INTEGER NOT NULL,
    gy                      INTEGER NOT NULL,
    cx                      INTEGER NOT NULL,
    cy                      INTEGER NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'pending',
    priority                REAL NOT NULL DEFAULT 0,
    content_hash            TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- cell_states (состояния ячеек map_cell_patches)
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
-- transitions (physical aggregate shared by generator, SQL and pack)
-- Defaults/behavior are supplied by the Transition POJO, not by source second SQL registry.
-- ============================================================
CREATE TABLE IF NOT EXISTS transitions (
    transition_uid         TEXT PRIMARY KEY NOT NULL,
    world_uid              TEXT NOT NULL REFERENCES worlds(world_uid),
    system_transition_type TEXT NOT NULL CHECK (length(system_transition_type) > 0),
    origin                 TEXT NOT NULL CHECK (origin IN ('authored', 'generated', 'runtime')),
    is_bidirectional       INTEGER NOT NULL CHECK (is_bidirectional IN (0, 1)),
    is_active              INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    access_mechanic         TEXT NOT NULL CHECK (json_valid(access_mechanic) AND json_type(access_mechanic) = 'array'),
    type_params            TEXT NOT NULL CHECK (json_valid(type_params) AND json_type(type_params) = 'object'),
    display_name           TEXT,
    glossary_ref           TEXT,
    tag_refs               TEXT NOT NULL CHECK (json_valid(tag_refs) AND json_type(tag_refs) = 'array'),
    source_space                TEXT NOT NULL CHECK (source_space IN ('surface', 'level')),
    source_level_uid            TEXT REFERENCES location_levels(level_uid),
    source_host_location_uid    TEXT REFERENCES named_locations(location_uid),
    source_node_uid             TEXT REFERENCES connection_nodes(node_uid),
    source_x                    INTEGER,
    source_y                    INTEGER,
    source_z                    INTEGER,
    destination_space                TEXT NOT NULL CHECK (destination_space IN ('surface', 'level')),
    destination_level_uid            TEXT REFERENCES location_levels(level_uid),
    destination_host_location_uid    TEXT REFERENCES named_locations(location_uid),
    destination_node_uid             TEXT REFERENCES connection_nodes(node_uid),
    destination_x                    INTEGER,
    destination_y                    INTEGER,
    destination_z                    INTEGER,
    CHECK ((source_space = 'surface' AND source_level_uid IS NULL) OR
           (source_space = 'level' AND source_level_uid IS NOT NULL AND source_x IS NOT NULL AND source_y IS NOT NULL AND source_z IS NOT NULL)),
    CHECK ((destination_space = 'surface' AND destination_level_uid IS NULL) OR
           (destination_space = 'level' AND destination_level_uid IS NOT NULL AND destination_x IS NOT NULL AND destination_y IS NOT NULL AND destination_z IS NOT NULL)),
    CHECK ((source_x IS NULL AND source_y IS NULL AND source_z IS NULL) OR
           (typeof(source_x) = 'integer' AND typeof(source_y) = 'integer' AND typeof(source_z) = 'integer')),
    CHECK ((destination_x IS NULL AND destination_y IS NULL AND destination_z IS NULL) OR
           (typeof(destination_x) = 'integer' AND typeof(destination_y) = 'integer' AND typeof(destination_z) = 'integer'))
);

CREATE TABLE IF NOT EXISTS transition_sides (
    transition_uid            TEXT NOT NULL REFERENCES transitions(transition_uid) ON DELETE CASCADE,
    side                      TEXT NOT NULL CHECK (side IN ('source', 'destination')),
    owner_location_uid        TEXT REFERENCES named_locations(location_uid),
    is_discovered             INTEGER NOT NULL CHECK (is_discovered IN (0, 1)),
    is_accessible             INTEGER NOT NULL CHECK (is_accessible IN (0, 1)),
    entry_difficulty_override INTEGER CHECK (entry_difficulty_override IS NULL OR
                                           (typeof(entry_difficulty_override) = 'integer' AND entry_difficulty_override BETWEEN 0 AND 100)),
    guard_level_override      INTEGER CHECK (guard_level_override IS NULL OR
                                           (typeof(guard_level_override) = 'integer' AND guard_level_override BETWEEN 0 AND 100)),
    display_name              TEXT,
    PRIMARY KEY (transition_uid, side)
);

CREATE INDEX IF NOT EXISTS idx_transitions_world ON transitions(world_uid);
CREATE INDEX IF NOT EXISTS idx_transitions_source_level ON transitions(world_uid, source_level_uid);
CREATE INDEX IF NOT EXISTS idx_transitions_destination_level ON transitions(world_uid, destination_level_uid);
CREATE INDEX IF NOT EXISTS idx_transitions_source_node ON transitions(world_uid, source_node_uid);
CREATE INDEX IF NOT EXISTS idx_transitions_destination_node ON transitions(world_uid, destination_node_uid);
CREATE INDEX IF NOT EXISTS idx_transition_sides_owner ON transition_sides(owner_location_uid, side, transition_uid);

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
    traversal_conditions TEXT,              -- JSON: dict
    relief_pick_policy  TEXT                -- JSON: ObjectReliefPickPolicy (R31 road_shoulder)
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
-- relief_grade_systems  (R36l: ≥2 grades; 1 grade → no system row)
-- ============================================================
CREATE TABLE IF NOT EXISTS relief_grade_systems (
    grade_system_uid TEXT PRIMARY KEY,
    world_uid        TEXT NOT NULL,
    grade_instance_uids TEXT NOT NULL,       -- JSON ordered ReliefGradeInstance.grade_uid, len ≥ 2
    created_at       TEXT NOT NULL,
    owner_uid        TEXT,                   -- edge uid or ribbon context token (not FK)
    display_name     TEXT,
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid)
);

-- ============================================================
-- relief_grade_instances  (R36j: one constant-angle Grade ≈ MountainSpec)
-- ============================================================
CREATE TABLE IF NOT EXISTS relief_grade_instances (
    grade_uid        TEXT PRIMARY KEY,
    world_uid        TEXT NOT NULL,
    kind             TEXT NOT NULL,          -- SLOPE | SHEER
    height_cells     INTEGER NOT NULL,
    length_cells     INTEGER NOT NULL,
    cell_refs        TEXT NOT NULL,          -- JSON [[lx,ly], ...] light-grid
    created_at       TEXT NOT NULL,
    angle_deg        REAL,                   -- honest θ SLOPE and SHEER
    facing           TEXT,                   -- NULL / none for SHEER
    earthen_canal    INTEGER NOT NULL DEFAULT 0,
    structure_refs   TEXT,                   -- JSON ["barrier_ref", ...] (BAR-1)
    structure_canal  TEXT,                   -- canal_template_registry system_type
    template_uid     TEXT,
    owner_uid        TEXT,                   -- edge uid or ribbon context token (not FK)
    site_id          TEXT,
    grade_system_uid TEXT,
    FOREIGN KEY (world_uid)        REFERENCES worlds(world_uid),
    FOREIGN KEY (template_uid)     REFERENCES relief_templates(template_uid),
    FOREIGN KEY (grade_system_uid) REFERENCES relief_grade_systems(grade_system_uid)
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



CREATE INDEX IF NOT EXISTS idx_factions_world           ON factions (world_uid);

CREATE INDEX IF NOT EXISTS idx_named_locations_world    ON named_locations (world_uid);
CREATE INDEX IF NOT EXISTS idx_named_locations_parent   ON named_locations (parent_location_uid);
CREATE INDEX IF NOT EXISTS idx_named_locations_type     ON named_locations (world_uid, system_location_type);
CREATE INDEX IF NOT EXISTS idx_named_locations_public   ON named_locations (world_uid, is_public);

CREATE INDEX IF NOT EXISTS idx_map_cell_patches_location_z ON map_cell_patches (world_uid, location_uid, z);

CREATE INDEX IF NOT EXISTS idx_location_levels_location ON location_levels (location_uid);

CREATE INDEX IF NOT EXISTS idx_map_cell_patches_location ON map_cell_patches (world_uid, location_uid, z);
CREATE INDEX IF NOT EXISTS idx_map_cell_patches_xy       ON map_cell_patches (world_uid, x, y);
CREATE INDEX IF NOT EXISTS idx_map_cell_patches_grade    ON map_cell_patches (world_uid, system_grade_uid);
CREATE INDEX IF NOT EXISTS idx_relief_grade_instances_world ON relief_grade_instances (world_uid);
CREATE INDEX IF NOT EXISTS idx_relief_grade_systems_world   ON relief_grade_systems (world_uid);
CREATE INDEX IF NOT EXISTS idx_chunk_refine_jobs_world   ON chunk_refine_jobs (world_uid, status);

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

CREATE INDEX IF NOT EXISTS idx_library_packs_owner       ON library_packs (owner_world_uid);
CREATE INDEX IF NOT EXISTS idx_library_packs_source      ON library_packs (source_pack_uid);
CREATE INDEX IF NOT EXISTS idx_library_pack_members_pack ON library_pack_members (pack_uid);
CREATE INDEX IF NOT EXISTS idx_library_pack_deps_required ON library_pack_dependencies (required_pack_uid);

-- Snapshot core: append-only identities and facts; publication IO stays in adapters.
CREATE TABLE IF NOT EXISTS world_publications (
    publication_id TEXT NOT NULL PRIMARY KEY CHECK (publication_id IS NULL OR (length(publication_id) > 0)),
    world_uid TEXT NOT NULL CHECK (world_uid IS NULL OR (length(world_uid) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    publication_seq INTEGER NOT NULL CHECK (publication_seq IS NULL OR (typeof(publication_seq) = 'integer' AND publication_seq >= 1)),
    operation_id TEXT CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    pack_hash TEXT CHECK (pack_hash IS NULL OR (length(pack_hash) = 64 AND pack_hash NOT GLOB '*[^0-9a-f]*')),
    snapshot_head_id TEXT CHECK (snapshot_head_id IS NULL OR (length(snapshot_head_id) > 0)),
    active_timeline_id TEXT CHECK (active_timeline_id IS NULL OR (length(active_timeline_id) > 0)),
    gameplay_started INTEGER NOT NULL CHECK (gameplay_started IS NULL OR (typeof(gameplay_started) = 'integer' AND gameplay_started IN (0,1))),
    UNIQUE (world_uid, publication_id),
    UNIQUE (world_uid, publication_seq),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid),
    FOREIGN KEY (world_uid, predecessor_id) REFERENCES world_publications(world_uid, publication_id) ON DELETE RESTRICT,
    FOREIGN KEY (world_uid, operation_id) REFERENCES publication_operations(world_uid, operation_id),
    FOREIGN KEY (world_uid, snapshot_head_id) REFERENCES world_snapshots(world_uid, snapshot_id),
    FOREIGN KEY (world_uid, active_timeline_id) REFERENCES timelines(world_uid, timeline_id),
    CHECK (gameplay_started = 1 OR snapshot_head_id IS NULL),
    CHECK (gameplay_started = 0 OR (pack_hash IS NOT NULL AND active_timeline_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS player_publications (
    publication_id TEXT NOT NULL PRIMARY KEY CHECK (publication_id IS NULL OR (length(publication_id) > 0)),
    player_uid TEXT NOT NULL CHECK (player_uid IS NULL OR (length(player_uid) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    publication_seq INTEGER NOT NULL CHECK (publication_seq IS NULL OR (typeof(publication_seq) = 'integer' AND publication_seq >= 1)),
    player_snapshot_id TEXT NOT NULL CHECK (player_snapshot_id IS NULL OR (length(player_snapshot_id) > 0)),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    UNIQUE (player_uid, publication_id),
    UNIQUE (player_uid, publication_seq),
    FOREIGN KEY (player_uid) REFERENCES character_sheet(character_uid),
    FOREIGN KEY (player_uid, predecessor_id) REFERENCES player_publications(player_uid, publication_id) ON DELETE RESTRICT,
    FOREIGN KEY (player_uid, player_snapshot_id) REFERENCES player_snapshots(player_uid, player_snapshot_id),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id)
);

CREATE TABLE IF NOT EXISTS publication_operations (
    operation_id TEXT NOT NULL PRIMARY KEY CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    world_uid TEXT NOT NULL CHECK (world_uid IS NULL OR (length(world_uid) > 0)),
    kind TEXT NOT NULL CHECK (kind IS NULL OR (length(kind) > 0)),
    preparation_fingerprint TEXT NOT NULL CHECK (preparation_fingerprint IS NULL OR (length(preparation_fingerprint) = 64 AND preparation_fingerprint NOT GLOB '*[^0-9a-f]*')),
    UNIQUE (world_uid, operation_id),
    FOREIGN KEY (world_uid) REFERENCES worlds(world_uid),
    CHECK (kind IN ('snapshot_apply', 'pack_activation', 'gameplay_start'))
);

CREATE TABLE IF NOT EXISTS publication_requests (
    operation_id TEXT NOT NULL PRIMARY KEY CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    publication_fingerprint TEXT NOT NULL CHECK (publication_fingerprint IS NULL OR (length(publication_fingerprint) = 64 AND publication_fingerprint NOT GLOB '*[^0-9a-f]*')),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id)
);

CREATE TABLE IF NOT EXISTS publication_operation_events (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (event_id IS NULL OR (length(event_id) > 0)),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    event_seq INTEGER NOT NULL CHECK (event_seq IS NULL OR (typeof(event_seq) = 'integer' AND event_seq >= 1)),
    phase TEXT NOT NULL CHECK (phase IS NULL OR (length(phase) > 0)),
    fence INTEGER NOT NULL CHECK (fence IS NULL OR (typeof(fence) = 'integer' AND fence >= 1)),
    UNIQUE (operation_id, event_id),
    UNIQUE (operation_id, event_seq),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id),
    FOREIGN KEY (operation_id, predecessor_id) REFERENCES publication_operation_events(operation_id, event_id),
    CHECK (phase IN ('preparing','ready','applying','terminal','recovery_required'))
);

CREATE TABLE IF NOT EXISTS publication_outcomes (
    operation_id TEXT NOT NULL PRIMARY KEY CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    outcome_kind TEXT NOT NULL CHECK (outcome_kind IS NULL OR (length(outcome_kind) > 0)),
    category TEXT CHECK (category IS NULL OR (length(category) > 0)),
    format_version INTEGER NOT NULL CHECK (format_version IS NULL OR (typeof(format_version) = 'integer' AND format_version >= 1)),
    outcome_data BLOB NOT NULL CHECK (typeof(outcome_data) = 'blob' AND length(outcome_data) > 0),
    outcome_checksum TEXT NOT NULL CHECK (outcome_checksum IS NULL OR (length(outcome_checksum) = 64 AND outcome_checksum NOT GLOB '*[^0-9a-f]*')),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id),
    CHECK (outcome_kind IN ('snapshot_apply','pack_activation','gameplay_start','cancelled')),
    CHECK ((outcome_kind = 'snapshot_apply' AND category IS NOT NULL AND category IN ('committed','conflict','rejected')) OR (outcome_kind != 'snapshot_apply' AND category IS NULL))
);

CREATE TABLE IF NOT EXISTS player_snapshots (
    player_snapshot_id TEXT NOT NULL PRIMARY KEY CHECK (player_snapshot_id IS NULL OR (length(player_snapshot_id) > 0)),
    player_uid TEXT NOT NULL CHECK (player_uid IS NULL OR (length(player_uid) > 0)),
    world_uid TEXT NOT NULL CHECK (world_uid IS NULL OR (length(world_uid) > 0)),
    timeline_id TEXT NOT NULL CHECK (timeline_id IS NULL OR (length(timeline_id) > 0)),
    session_id TEXT CHECK (session_id IS NULL OR (length(session_id) > 0)),
    turn_id INTEGER NOT NULL CHECK (turn_id IS NULL OR (typeof(turn_id) = 'integer' AND turn_id >= 1)),
    created_at TEXT NOT NULL CHECK (created_at IS NULL OR (length(created_at) > 0)),
    parent_player_snapshot_id TEXT CHECK (parent_player_snapshot_id IS NULL OR (length(parent_player_snapshot_id) > 0)),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    envelope_format_version INTEGER NOT NULL CHECK (envelope_format_version IS NULL OR (typeof(envelope_format_version) = 'integer' AND envelope_format_version >= 1)),
    snapshot_data BLOB NOT NULL CHECK (typeof(snapshot_data) = 'blob' AND length(snapshot_data) > 0),
    snapshot_checksum TEXT NOT NULL CHECK (snapshot_checksum IS NULL OR (length(snapshot_checksum) = 64 AND snapshot_checksum NOT GLOB '*[^0-9a-f]*')),
    UNIQUE (player_uid, player_snapshot_id),
    UNIQUE (operation_id, player_uid),
    FOREIGN KEY (player_uid) REFERENCES character_sheet(character_uid),
    FOREIGN KEY (session_id) REFERENCES game_sessions(id),
    FOREIGN KEY (player_uid, parent_player_snapshot_id) REFERENCES player_snapshots(player_uid, player_snapshot_id) ON DELETE RESTRICT,
    FOREIGN KEY (world_uid, timeline_id, operation_id) REFERENCES world_snapshots(world_uid, timeline_id, operation_id)
);

CREATE TABLE IF NOT EXISTS artifact_catalog (
    artifact_id TEXT NOT NULL PRIMARY KEY CHECK (artifact_id IS NULL OR (length(artifact_id) > 0)),
    kind TEXT NOT NULL CHECK (kind IS NULL OR (length(kind) > 0)),
    format_key TEXT NOT NULL CHECK (format_key IS NULL OR (length(format_key) > 0)),
    format_version INTEGER NOT NULL CHECK (format_version IS NULL OR (typeof(format_version) = 'integer' AND format_version >= 1)),
    content_hash TEXT NOT NULL CHECK (content_hash IS NULL OR (length(content_hash) = 64 AND content_hash NOT GLOB '*[^0-9a-f]*')),
    nbytes INTEGER NOT NULL CHECK (nbytes IS NULL OR (typeof(nbytes) = 'integer' AND nbytes >= 0)),
    row_count INTEGER CHECK (row_count IS NULL OR (typeof(row_count) = 'integer' AND row_count >= 0)),
    UNIQUE (kind, format_key, format_version, content_hash),
    CHECK (kind IN ('blob','sql_rows')),
    CHECK ((kind = 'blob' AND row_count IS NULL) OR (kind = 'sql_rows' AND row_count IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS artifact_storage_events (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (event_id IS NULL OR (length(event_id) > 0)),
    artifact_id TEXT NOT NULL CHECK (artifact_id IS NULL OR (length(artifact_id) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    event_seq INTEGER NOT NULL CHECK (event_seq IS NULL OR (typeof(event_seq) = 'integer' AND event_seq >= 1)),
    kind TEXT NOT NULL CHECK (kind IS NULL OR (length(kind) > 0)),
    UNIQUE (artifact_id, event_id),
    UNIQUE (artifact_id, event_seq),
    FOREIGN KEY (artifact_id) REFERENCES artifact_catalog(artifact_id),
    FOREIGN KEY (artifact_id, predecessor_id) REFERENCES artifact_storage_events(artifact_id, event_id),
    CHECK (kind IN ('sealed','gc_deleted'))
);

CREATE TABLE IF NOT EXISTS artifact_holder_events (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (event_id IS NULL OR (length(event_id) > 0)),
    artifact_id TEXT NOT NULL CHECK (artifact_id IS NULL OR (length(artifact_id) > 0)),
    holder_kind TEXT NOT NULL CHECK (holder_kind IS NULL OR (length(holder_kind) > 0)),
    operation_id TEXT CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    fence INTEGER CHECK (fence IS NULL OR (typeof(fence) = 'integer' AND fence >= 1)),
    retained_artifact_id TEXT CHECK (retained_artifact_id IS NULL OR (length(retained_artifact_id) > 0)),
    world_snapshot_id TEXT CHECK (world_snapshot_id IS NULL OR (length(world_snapshot_id) > 0)),
    player_snapshot_id TEXT CHECK (player_snapshot_id IS NULL OR (length(player_snapshot_id) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    event_seq INTEGER NOT NULL CHECK (event_seq IS NULL OR (typeof(event_seq) = 'integer' AND event_seq >= 1)),
    event_kind TEXT NOT NULL CHECK (event_kind IS NULL OR (length(event_kind) > 0)),
    UNIQUE (artifact_id, event_id),
    FOREIGN KEY (artifact_id) REFERENCES artifact_catalog(artifact_id),
    FOREIGN KEY (artifact_id, predecessor_id) REFERENCES artifact_holder_events(artifact_id, event_id),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id),
    FOREIGN KEY (retained_artifact_id) REFERENCES artifact_catalog(artifact_id),
    FOREIGN KEY (world_snapshot_id) REFERENCES world_snapshots(snapshot_id),
    FOREIGN KEY (player_snapshot_id) REFERENCES player_snapshots(player_snapshot_id),
    CHECK (event_kind IN ('acquire','release')),
    CHECK ((holder_kind = 'operation' AND operation_id IS NOT NULL AND fence IS NOT NULL AND retained_artifact_id IS NULL AND world_snapshot_id IS NULL AND player_snapshot_id IS NULL) OR (holder_kind = 'artifact' AND retained_artifact_id IS NOT NULL AND operation_id IS NULL AND fence IS NULL AND world_snapshot_id IS NULL AND player_snapshot_id IS NULL) OR (holder_kind = 'snapshot' AND operation_id IS NULL AND fence IS NULL AND retained_artifact_id IS NULL AND ((world_snapshot_id IS NOT NULL AND player_snapshot_id IS NULL) OR (world_snapshot_id IS NULL AND player_snapshot_id IS NOT NULL))))
);

CREATE TABLE IF NOT EXISTS artifact_lease_events (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (event_id IS NULL OR (length(event_id) > 0)),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    event_seq INTEGER NOT NULL CHECK (event_seq IS NULL OR (typeof(event_seq) = 'integer' AND event_seq >= 1)),
    fence INTEGER NOT NULL CHECK (fence IS NULL OR (typeof(fence) = 'integer' AND fence >= 1)),
    admission_open INTEGER NOT NULL CHECK (admission_open IS NULL OR (typeof(admission_open) = 'integer' AND admission_open IN (0,1))),
    UNIQUE (operation_id, event_id),
    UNIQUE (operation_id, event_seq),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id),
    FOREIGN KEY (operation_id, predecessor_id) REFERENCES artifact_lease_events(operation_id, event_id)
);

CREATE TABLE IF NOT EXISTS artifact_writer_claims (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (event_id IS NULL OR (length(event_id) > 0)),
    artifact_id TEXT NOT NULL CHECK (artifact_id IS NULL OR (length(artifact_id) > 0)),
    operation_id TEXT NOT NULL CHECK (operation_id IS NULL OR (length(operation_id) > 0)),
    fence INTEGER NOT NULL CHECK (fence IS NULL OR (typeof(fence) = 'integer' AND fence >= 1)),
    predecessor_id TEXT CHECK (predecessor_id IS NULL OR (length(predecessor_id) > 0)),
    event_seq INTEGER NOT NULL CHECK (event_seq IS NULL OR (typeof(event_seq) = 'integer' AND event_seq >= 1)),
    event_kind TEXT NOT NULL CHECK (event_kind IS NULL OR (length(event_kind) > 0)),
    UNIQUE (artifact_id, event_id),
    UNIQUE (artifact_id, operation_id, fence, event_seq),
    FOREIGN KEY (artifact_id) REFERENCES artifact_catalog(artifact_id),
    FOREIGN KEY (operation_id) REFERENCES publication_operations(operation_id),
    FOREIGN KEY (artifact_id, predecessor_id) REFERENCES artifact_writer_claims(artifact_id, event_id),
    CHECK (event_kind IN ('acquire','release'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_world_publications_root ON world_publications (world_uid) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_world_publications_operation ON world_publications (operation_id) WHERE operation_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_world_publications_successor ON world_publications (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_world_publications_latest ON world_publications (world_uid, publication_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_player_publications_root ON player_publications (player_uid) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_player_publications_operation ON player_publications (operation_id, player_uid);
CREATE UNIQUE INDEX IF NOT EXISTS ux_player_publications_successor ON player_publications (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_player_publications_latest ON player_publications (player_uid, publication_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_publication_operation_events_root ON publication_operation_events (operation_id) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_publication_operation_events_successor ON publication_operation_events (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_publication_operation_events_latest ON publication_operation_events (operation_id, event_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_storage_events_root ON artifact_storage_events (artifact_id) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_storage_events_successor ON artifact_storage_events (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_artifact_storage_events_latest ON artifact_storage_events (artifact_id, event_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_lease_events_root ON artifact_lease_events (operation_id) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_lease_events_successor ON artifact_lease_events (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_artifact_lease_events_latest ON artifact_lease_events (operation_id, event_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_holder_events_root ON artifact_holder_events (artifact_id, holder_kind, COALESCE(operation_id,''), COALESCE(fence,0), COALESCE(retained_artifact_id,''), COALESCE(world_snapshot_id,''), COALESCE(player_snapshot_id,'')) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_holder_events_successor ON artifact_holder_events (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_artifact_holder_events_latest ON artifact_holder_events (artifact_id, holder_kind, COALESCE(operation_id,''), COALESCE(fence,0), COALESCE(retained_artifact_id,''), COALESCE(world_snapshot_id,''), COALESCE(player_snapshot_id,''), event_seq DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_holder_sequence ON artifact_holder_events (artifact_id, holder_kind, COALESCE(operation_id,''), COALESCE(fence,0), COALESCE(retained_artifact_id,''), COALESCE(world_snapshot_id,''), COALESCE(player_snapshot_id,''), event_seq);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_writer_claims_root ON artifact_writer_claims (artifact_id, operation_id, fence) WHERE predecessor_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_writer_claims_successor ON artifact_writer_claims (predecessor_id) WHERE predecessor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_artifact_writer_claims_latest ON artifact_writer_claims (artifact_id, operation_id, fence, event_seq DESC);
CREATE TRIGGER IF NOT EXISTS world_publications_no_update BEFORE UPDATE ON world_publications BEGIN SELECT RAISE(ABORT, 'append-only world_publications'); END;
CREATE TRIGGER IF NOT EXISTS world_publications_no_delete BEFORE DELETE ON world_publications BEGIN SELECT RAISE(ABORT, 'append-only world_publications'); END;
CREATE TRIGGER IF NOT EXISTS player_publications_no_update BEFORE UPDATE ON player_publications BEGIN SELECT RAISE(ABORT, 'append-only player_publications'); END;
CREATE TRIGGER IF NOT EXISTS player_publications_no_delete BEFORE DELETE ON player_publications BEGIN SELECT RAISE(ABORT, 'append-only player_publications'); END;
CREATE TRIGGER IF NOT EXISTS publication_operations_no_update BEFORE UPDATE ON publication_operations BEGIN SELECT RAISE(ABORT, 'append-only publication_operations'); END;
CREATE TRIGGER IF NOT EXISTS publication_operations_no_delete BEFORE DELETE ON publication_operations BEGIN SELECT RAISE(ABORT, 'append-only publication_operations'); END;
CREATE TRIGGER IF NOT EXISTS publication_requests_no_update BEFORE UPDATE ON publication_requests BEGIN SELECT RAISE(ABORT, 'append-only publication_requests'); END;
CREATE TRIGGER IF NOT EXISTS publication_requests_no_delete BEFORE DELETE ON publication_requests BEGIN SELECT RAISE(ABORT, 'append-only publication_requests'); END;
CREATE TRIGGER IF NOT EXISTS publication_operation_events_no_update BEFORE UPDATE ON publication_operation_events BEGIN SELECT RAISE(ABORT, 'append-only publication_operation_events'); END;
CREATE TRIGGER IF NOT EXISTS publication_operation_events_no_delete BEFORE DELETE ON publication_operation_events BEGIN SELECT RAISE(ABORT, 'append-only publication_operation_events'); END;
CREATE TRIGGER IF NOT EXISTS publication_outcomes_no_update BEFORE UPDATE ON publication_outcomes BEGIN SELECT RAISE(ABORT, 'append-only publication_outcomes'); END;
CREATE TRIGGER IF NOT EXISTS publication_outcomes_no_delete BEFORE DELETE ON publication_outcomes BEGIN SELECT RAISE(ABORT, 'append-only publication_outcomes'); END;
CREATE TRIGGER IF NOT EXISTS world_snapshots_no_update BEFORE UPDATE ON world_snapshots BEGIN SELECT RAISE(ABORT, 'append-only world_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS world_snapshots_no_delete BEFORE DELETE ON world_snapshots BEGIN SELECT RAISE(ABORT, 'append-only world_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS player_snapshots_no_update BEFORE UPDATE ON player_snapshots BEGIN SELECT RAISE(ABORT, 'append-only player_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS player_snapshots_no_delete BEFORE DELETE ON player_snapshots BEGIN SELECT RAISE(ABORT, 'append-only player_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS artifact_catalog_no_update BEFORE UPDATE ON artifact_catalog BEGIN SELECT RAISE(ABORT, 'append-only artifact_catalog'); END;
CREATE TRIGGER IF NOT EXISTS artifact_catalog_no_delete BEFORE DELETE ON artifact_catalog BEGIN SELECT RAISE(ABORT, 'append-only artifact_catalog'); END;
CREATE TRIGGER IF NOT EXISTS artifact_storage_events_no_update BEFORE UPDATE ON artifact_storage_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_storage_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_storage_events_no_delete BEFORE DELETE ON artifact_storage_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_storage_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_holder_events_no_update BEFORE UPDATE ON artifact_holder_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_holder_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_holder_events_no_delete BEFORE DELETE ON artifact_holder_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_holder_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_lease_events_no_update BEFORE UPDATE ON artifact_lease_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_lease_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_lease_events_no_delete BEFORE DELETE ON artifact_lease_events BEGIN SELECT RAISE(ABORT, 'append-only artifact_lease_events'); END;
CREATE TRIGGER IF NOT EXISTS artifact_writer_claims_no_update BEFORE UPDATE ON artifact_writer_claims BEGIN SELECT RAISE(ABORT, 'append-only artifact_writer_claims'); END;
CREATE TRIGGER IF NOT EXISTS artifact_writer_claims_no_delete BEFORE DELETE ON artifact_writer_claims BEGIN SELECT RAISE(ABORT, 'append-only artifact_writer_claims'); END;

-- Guards operate on immutable current facts; adapters still own transaction/capability proofs.
CREATE TRIGGER IF NOT EXISTS world_publications_identity_insert BEFORE INSERT ON world_publications
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM world_publications WHERE publication_id = NEW.publication_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS player_publications_identity_insert BEFORE INSERT ON player_publications
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM player_publications WHERE publication_id = NEW.publication_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_operations_identity_insert BEFORE INSERT ON publication_operations
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM publication_operations WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_requests_identity_insert BEFORE INSERT ON publication_requests
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM publication_requests WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_operation_events_identity_insert BEFORE INSERT ON publication_operation_events
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM publication_operation_events WHERE event_id = NEW.event_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_outcomes_identity_insert BEFORE INSERT ON publication_outcomes
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM publication_outcomes WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS world_snapshots_identity_insert BEFORE INSERT ON world_snapshots
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM world_snapshots WHERE snapshot_id = NEW.snapshot_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS player_snapshots_identity_insert BEFORE INSERT ON player_snapshots
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM player_snapshots WHERE player_snapshot_id = NEW.player_snapshot_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_catalog_identity_insert BEFORE INSERT ON artifact_catalog
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_catalog WHERE artifact_id = NEW.artifact_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_storage_events_identity_insert BEFORE INSERT ON artifact_storage_events
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_storage_events WHERE event_id = NEW.event_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_holder_events_identity_insert BEFORE INSERT ON artifact_holder_events
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_holder_events WHERE event_id = NEW.event_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_lease_events_identity_insert BEFORE INSERT ON artifact_lease_events
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_lease_events WHERE event_id = NEW.event_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_writer_claims_identity_insert BEFORE INSERT ON artifact_writer_claims
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_writer_claims WHERE event_id = NEW.event_id) THEN RAISE(ABORT, 'immutable identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS world_publications_sequence BEFORE INSERT ON world_publications
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.publication_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM world_publications p WHERE p.publication_id = NEW.predecessor_id AND NEW.publication_seq = p.publication_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM world_publications WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS player_publications_sequence BEFORE INSERT ON player_publications
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.publication_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM player_publications p WHERE p.publication_id = NEW.predecessor_id AND NEW.publication_seq = p.publication_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM player_publications WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_operation_events_sequence BEFORE INSERT ON publication_operation_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.event_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM publication_operation_events p WHERE p.event_id = NEW.predecessor_id AND NEW.event_seq = p.event_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM publication_operation_events WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_storage_events_sequence BEFORE INSERT ON artifact_storage_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.event_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_storage_events p WHERE p.event_id = NEW.predecessor_id AND NEW.event_seq = p.event_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM artifact_storage_events WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_holder_events_sequence BEFORE INSERT ON artifact_holder_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.event_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_holder_events p WHERE p.event_id = NEW.predecessor_id AND NEW.event_seq = p.event_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM artifact_holder_events WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_lease_events_sequence BEFORE INSERT ON artifact_lease_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.event_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_lease_events p WHERE p.event_id = NEW.predecessor_id AND NEW.event_seq = p.event_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM artifact_lease_events WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_writer_claims_sequence BEFORE INSERT ON artifact_writer_claims
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND NEW.event_seq != 1 THEN RAISE(ABORT, 'root sequence must be one') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims p WHERE p.event_id = NEW.predecessor_id AND NEW.event_seq = p.event_seq + 1) THEN RAISE(ABORT, 'invalid predecessor sequence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND EXISTS (SELECT 1 FROM artifact_writer_claims WHERE predecessor_id = NEW.predecessor_id) THEN RAISE(ABORT, 'predecessor already has a successor') END;

END;

CREATE TRIGGER IF NOT EXISTS world_publications_transition BEFORE INSERT ON world_publications
BEGIN
    SELECT CASE WHEN NEW.operation_id IS NOT NULL AND EXISTS (SELECT 1 FROM world_publications WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'operation already has a world publication') END;
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (EXISTS (SELECT 1 FROM world_publications WHERE world_uid = NEW.world_uid) OR NEW.operation_id IS NOT NULL OR NEW.pack_hash IS NOT NULL OR NEW.snapshot_head_id IS NOT NULL OR NEW.active_timeline_id IS NOT NULL OR NEW.gameplay_started != 0) THEN RAISE(ABORT, 'bootstrap requires an empty publication root') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND (NEW.operation_id IS NULL OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'applying' OR NOT EXISTS (SELECT 1 FROM publication_requests WHERE operation_id = NEW.operation_id)) THEN RAISE(ABORT, 'publication requires an applying bound operation') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM world_publications p WHERE p.publication_id = NEW.predecessor_id AND p.world_uid = NEW.world_uid AND (
        (p.gameplay_started = 0 AND NEW.gameplay_started = 0 AND (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) = 'pack_activation'
          AND NEW.pack_hash IS NOT NULL AND NEW.snapshot_head_id IS NULL AND NEW.active_timeline_id IS NULL)
        OR (p.gameplay_started = 0 AND NEW.gameplay_started = 1 AND (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) = 'gameplay_start'
          AND p.pack_hash IS NOT NULL AND NEW.pack_hash = p.pack_hash AND NEW.snapshot_head_id IS NULL AND NEW.active_timeline_id IS NOT NULL)
        OR (p.gameplay_started = 1 AND NEW.gameplay_started = 1 AND (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) = 'snapshot_apply'
          AND NEW.pack_hash = p.pack_hash AND NEW.active_timeline_id = p.active_timeline_id
          AND EXISTS (SELECT 1 FROM world_snapshots s WHERE s.snapshot_id = NEW.snapshot_head_id
            AND s.operation_id = NEW.operation_id AND s.world_uid = NEW.world_uid AND s.timeline_id = NEW.active_timeline_id
            AND s.parent_snapshot_id IS p.snapshot_head_id))
      )) THEN RAISE(ABORT, 'invalid publication transition') END;

END;

CREATE TRIGGER IF NOT EXISTS world_snapshots_insert_guard BEFORE INSERT ON world_snapshots
BEGIN
    SELECT CASE WHEN (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) IS NOT 'snapshot_apply' OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'applying' THEN RAISE(ABORT, 'snapshot requires applying snapshot operation') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM world_snapshots WHERE operation_id = NEW.operation_id OR (timeline_id = NEW.timeline_id AND turn_id = NEW.turn_id)) THEN RAISE(ABORT, 'snapshot tick already exists') END;
    SELECT CASE WHEN NOT EXISTS (
      SELECT 1 FROM world_publications p LEFT JOIN world_snapshots parent ON parent.snapshot_id = p.snapshot_head_id
      WHERE p.world_uid = NEW.world_uid AND p.publication_seq = (SELECT MAX(publication_seq) FROM world_publications WHERE world_uid = NEW.world_uid)
        AND p.gameplay_started = 1 AND p.active_timeline_id = NEW.timeline_id AND p.pack_hash = NEW.base_pack_hash
        AND p.snapshot_head_id IS NEW.parent_snapshot_id
        AND NEW.turn_id = CASE WHEN parent.timeline_id = NEW.timeline_id THEN parent.turn_id + 1 ELSE 1 END
    ) THEN RAISE(ABORT, 'snapshot does not extend the pinned runtime base') END;

END;

CREATE TRIGGER IF NOT EXISTS player_snapshots_insert_guard BEFORE INSERT ON player_snapshots
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM player_snapshots WHERE operation_id = NEW.operation_id AND player_uid = NEW.player_uid) THEN RAISE(ABORT, 'player tick already exists') END;
    SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM character_sheet WHERE character_uid = NEW.player_uid AND world_uid = NEW.world_uid) THEN RAISE(ABORT, 'player belongs to another world') END;
    SELECT CASE WHEN NEW.parent_player_snapshot_id IS NOT (SELECT player_snapshot_id FROM player_publications WHERE player_uid = NEW.player_uid ORDER BY publication_seq DESC LIMIT 1) THEN RAISE(ABORT, 'player parent is not the current head') END;
    SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM world_snapshots WHERE operation_id = NEW.operation_id AND world_uid = NEW.world_uid AND timeline_id = NEW.timeline_id AND turn_id = NEW.turn_id) THEN RAISE(ABORT, 'player tick does not match its world tick') END;
    SELECT CASE WHEN NEW.session_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM game_sessions WHERE id = NEW.session_id AND world_uid = NEW.world_uid AND player_character_id = NEW.player_uid) THEN RAISE(ABORT, 'session audit owner mismatch') END;

END;

CREATE TRIGGER IF NOT EXISTS player_publications_insert_guard BEFORE INSERT ON player_publications
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM player_publications WHERE operation_id = NEW.operation_id AND player_uid = NEW.player_uid) THEN RAISE(ABORT, 'operation already has this player publication') END;
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND EXISTS (SELECT 1 FROM player_publications WHERE player_uid = NEW.player_uid) THEN RAISE(ABORT, 'player root already exists') END;
    SELECT CASE WHEN (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) IS NOT 'snapshot_apply' OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'applying' THEN RAISE(ABORT, 'player publication requires applying snapshot operation') END;
    SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM player_snapshots s WHERE s.player_snapshot_id = NEW.player_snapshot_id AND s.player_uid = NEW.player_uid AND s.operation_id = NEW.operation_id
      AND s.parent_player_snapshot_id IS (SELECT p.player_snapshot_id FROM player_publications p WHERE p.publication_id = NEW.predecessor_id)) THEN RAISE(ABORT, 'player publication does not extend its expected head') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_operation_events_transition BEFORE INSERT ON publication_operation_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (EXISTS (SELECT 1 FROM publication_operation_events WHERE operation_id = NEW.operation_id) OR NEW.fence != 1 OR NEW.phase NOT IN ('preparing','applying')) THEN RAISE(ABORT, 'invalid initial operation event') END;
    SELECT CASE WHEN NEW.phase = 'applying' AND NOT EXISTS (SELECT 1 FROM publication_requests WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'apply requires request binding') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM publication_operation_events p WHERE p.event_id = NEW.predecessor_id AND p.operation_id = NEW.operation_id AND (
        (p.phase = 'preparing' AND NEW.phase IN ('ready','terminal') AND NEW.fence = p.fence)
        OR (p.phase = 'ready' AND NEW.phase IN ('applying','terminal') AND NEW.fence = p.fence)
        OR (p.phase = 'applying' AND NEW.phase IN ('terminal','recovery_required') AND NEW.fence = p.fence)
        OR (p.phase = 'recovery_required' AND NEW.phase = 'terminal' AND NEW.fence = p.fence)
        OR (p.phase IN ('applying','recovery_required') AND NEW.phase = 'ready' AND NEW.fence = p.fence + 1)
      )) THEN RAISE(ABORT, 'invalid operation phase or fence transition') END;
    SELECT CASE WHEN (NEW.phase = 'terminal') != EXISTS (SELECT 1 FROM publication_outcomes WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'terminal event must match durable outcome') END;
    SELECT CASE WHEN NEW.phase = 'ready' AND (EXISTS (SELECT 1 FROM (SELECT c.* FROM artifact_writer_claims c WHERE c.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims n WHERE n.predecessor_id = c.event_id)) c WHERE c.operation_id = NEW.operation_id)
      OR EXISTS (SELECT 1 FROM (SELECT h.* FROM artifact_holder_events h WHERE h.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_holder_events n WHERE n.predecessor_id = h.event_id)) h WHERE h.operation_id = NEW.operation_id AND NOT EXISTS
        (SELECT 1 FROM artifact_storage_events s WHERE s.artifact_id = h.artifact_id AND s.kind = 'sealed'
          AND NOT EXISTS (SELECT 1 FROM artifact_storage_events n WHERE n.predecessor_id = s.event_id)))
      OR EXISTS (SELECT 1 FROM artifact_lease_events l WHERE l.operation_id = NEW.operation_id AND l.admission_open = 1
          AND NOT EXISTS (SELECT 1 FROM artifact_lease_events n WHERE n.predecessor_id = l.event_id))
    ) THEN RAISE(ABORT, 'ready requires sealed holds and drained closed writers') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NEW.fence > (SELECT fence FROM publication_operation_events WHERE event_id = NEW.predecessor_id)
      AND (EXISTS (SELECT 1 FROM world_snapshots WHERE operation_id = NEW.operation_id) OR EXISTS (SELECT 1 FROM world_publications WHERE operation_id = NEW.operation_id)
        OR EXISTS (SELECT 1 FROM player_publications WHERE operation_id = NEW.operation_id)) THEN RAISE(ABORT, 'cannot resume a published operation') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_requests_insert_guard BEFORE INSERT ON publication_requests
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM publication_outcomes WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'terminal request binding cannot be added') END;

END;

CREATE TRIGGER IF NOT EXISTS publication_outcomes_insert_guard BEFORE INSERT ON publication_outcomes
BEGIN
    SELECT CASE WHEN (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NULL OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) = 'terminal' THEN RAISE(ABORT, 'outcome requires a nonterminal operation') END;
    SELECT CASE WHEN NEW.outcome_kind != 'cancelled' AND NOT EXISTS (SELECT 1 FROM publication_requests WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'outcome requires request binding') END;
    SELECT CASE WHEN NEW.outcome_kind != 'cancelled' AND (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'applying' THEN RAISE(ABORT, 'publication outcome requires a claimed apply owner') END;
    SELECT CASE WHEN NEW.outcome_kind = 'cancelled' AND EXISTS (SELECT 1 FROM artifact_lease_events l WHERE l.operation_id = NEW.operation_id AND l.admission_open = 1 AND NOT EXISTS (SELECT 1 FROM artifact_lease_events n WHERE n.predecessor_id = l.event_id)) THEN RAISE(ABORT, 'cancellation requires closed writer admission') END;
    SELECT CASE WHEN NEW.outcome_kind IN ('pack_activation','gameplay_start') AND NEW.outcome_kind != (SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) THEN RAISE(ABORT, 'terminal kind does not match operation') END;
    SELECT CASE WHEN NEW.category = 'committed' AND ((SELECT kind FROM publication_operations WHERE operation_id = NEW.operation_id) IS NOT 'snapshot_apply' OR NOT EXISTS
      (SELECT 1 FROM world_publications WHERE operation_id = NEW.operation_id AND snapshot_head_id IS NOT NULL)
      OR EXISTS (SELECT 1 FROM player_snapshots s WHERE s.operation_id = NEW.operation_id AND NOT EXISTS
        (SELECT 1 FROM player_publications p WHERE p.operation_id = NEW.operation_id AND p.player_snapshot_id = s.player_snapshot_id))) THEN RAISE(ABORT, 'committed outcome requires all snapshot publications') END;
    SELECT CASE WHEN NEW.outcome_kind = 'gameplay_start' AND NOT EXISTS (SELECT 1 FROM world_publications WHERE operation_id = NEW.operation_id AND gameplay_started = 1 AND snapshot_head_id IS NULL) THEN RAISE(ABORT, 'gameplay outcome requires guard publication') END;
    SELECT CASE WHEN (NEW.category IN ('conflict','rejected') OR NEW.outcome_kind = 'cancelled') AND
      (EXISTS (SELECT 1 FROM world_snapshots WHERE operation_id = NEW.operation_id) OR EXISTS (SELECT 1 FROM world_publications WHERE operation_id = NEW.operation_id)
        OR EXISTS (SELECT 1 FROM player_snapshots WHERE operation_id = NEW.operation_id) OR EXISTS (SELECT 1 FROM player_publications WHERE operation_id = NEW.operation_id)
        OR EXISTS (SELECT 1 FROM (SELECT c.* FROM artifact_writer_claims c WHERE c.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims n WHERE n.predecessor_id = c.event_id)) c WHERE c.operation_id = NEW.operation_id)) THEN RAISE(ABORT, 'refusal or cancellation cannot hide published writes or live writers') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_catalog_identity_guard BEFORE INSERT ON artifact_catalog
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM artifact_catalog WHERE kind = NEW.kind AND format_key = NEW.format_key AND format_version = NEW.format_version AND content_hash = NEW.content_hash) THEN RAISE(ABORT, 'immutable content identity already exists') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_holder_events_insert_guard BEFORE INSERT ON artifact_holder_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (NEW.event_kind != 'acquire' OR EXISTS (SELECT 1 FROM artifact_holder_events p WHERE p.artifact_id = NEW.artifact_id AND p.holder_kind IS NEW.holder_kind AND p.operation_id IS NEW.operation_id AND p.fence IS NEW.fence AND p.retained_artifact_id IS NEW.retained_artifact_id AND p.world_snapshot_id IS NEW.world_snapshot_id AND p.player_snapshot_id IS NEW.player_snapshot_id)) THEN RAISE(ABORT, 'invalid holder root') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_holder_events p WHERE p.event_id = NEW.predecessor_id AND p.artifact_id = NEW.artifact_id AND p.holder_kind IS NEW.holder_kind AND p.operation_id IS NEW.operation_id AND p.fence IS NEW.fence AND p.retained_artifact_id IS NEW.retained_artifact_id AND p.world_snapshot_id IS NEW.world_snapshot_id AND p.player_snapshot_id IS NEW.player_snapshot_id AND p.event_kind != NEW.event_kind) THEN RAISE(ABORT, 'holder identity or transition mismatch') END;
    SELECT CASE WHEN NEW.holder_kind = 'snapshot' AND NEW.event_kind = 'release' THEN RAISE(ABORT, 'published history holds cannot be released') END;
    SELECT CASE WHEN NEW.event_kind = 'acquire' AND NEW.holder_kind = 'operation' AND
      ((SELECT fence FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT NEW.fence OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NULL OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) = 'terminal') THEN RAISE(ABORT, 'stale or closed operation holder') END;
    SELECT CASE WHEN NEW.event_kind = 'release' AND NEW.holder_kind = 'operation' AND
      (EXISTS (SELECT 1 FROM (SELECT c.* FROM artifact_writer_claims c WHERE c.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims n WHERE n.predecessor_id = c.event_id)) c WHERE c.operation_id = NEW.operation_id AND c.fence = NEW.fence)
      OR EXISTS (SELECT 1 FROM artifact_lease_events l WHERE l.operation_id = NEW.operation_id AND l.fence = NEW.fence AND l.admission_open = 1
        AND NOT EXISTS (SELECT 1 FROM artifact_lease_events n WHERE n.predecessor_id = l.event_id))) THEN RAISE(ABORT, 'operation hold requires closed drained writers') END;
    SELECT CASE WHEN NEW.event_kind = 'acquire' AND NEW.holder_kind != 'operation' AND NOT EXISTS
      (SELECT 1 FROM artifact_storage_events s WHERE s.artifact_id = NEW.artifact_id AND s.kind = 'sealed'
        AND NOT EXISTS (SELECT 1 FROM artifact_storage_events n WHERE n.predecessor_id = s.event_id)) THEN RAISE(ABORT, 'published or retention hold requires a sealed artifact') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_lease_events_insert_guard BEFORE INSERT ON artifact_lease_events
BEGIN
    SELECT CASE WHEN NEW.fence IS NOT (SELECT fence FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) THEN RAISE(ABORT, 'stale lease fence') END;
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (EXISTS (SELECT 1 FROM artifact_lease_events WHERE operation_id = NEW.operation_id) OR NEW.admission_open != 1 OR (SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'preparing') THEN RAISE(ABORT, 'invalid lease admission root') END;
    SELECT CASE WHEN NEW.admission_open = 1 AND ((SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'preparing' OR EXISTS (SELECT 1 FROM artifact_lease_events p WHERE p.event_id = NEW.predecessor_id AND p.admission_open = 0)) THEN RAISE(ABORT, 'writer admission cannot reopen') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_lease_events p WHERE p.event_id = NEW.predecessor_id AND p.operation_id = NEW.operation_id AND NEW.fence >= p.fence) THEN RAISE(ABORT, 'lease owner or fence mismatch') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_writer_claims_insert_guard BEFORE INSERT ON artifact_writer_claims
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (NEW.event_kind != 'acquire' OR EXISTS (SELECT 1 FROM artifact_writer_claims WHERE artifact_id = NEW.artifact_id AND operation_id = NEW.operation_id AND fence = NEW.fence)) THEN RAISE(ABORT, 'invalid writer root') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims p WHERE p.event_id = NEW.predecessor_id AND p.artifact_id = NEW.artifact_id AND p.operation_id = NEW.operation_id AND p.fence = NEW.fence AND p.event_kind != NEW.event_kind) THEN RAISE(ABORT, 'writer owner or transition mismatch') END;
    SELECT CASE WHEN NEW.event_kind = 'acquire' AND ((SELECT phase FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) IS NOT 'preparing' OR NEW.fence IS NOT (SELECT fence FROM publication_operation_events WHERE operation_id = NEW.operation_id ORDER BY event_seq DESC LIMIT 1) OR NOT EXISTS
      (SELECT 1 FROM artifact_lease_events l WHERE l.operation_id = NEW.operation_id AND l.fence = NEW.fence AND l.admission_open = 1
        AND NOT EXISTS (SELECT 1 FROM artifact_lease_events n WHERE n.predecessor_id = l.event_id))
      OR NOT EXISTS (SELECT 1 FROM (SELECT h.* FROM artifact_holder_events h WHERE h.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_holder_events n WHERE n.predecessor_id = h.event_id)) h WHERE h.artifact_id = NEW.artifact_id AND h.operation_id = NEW.operation_id AND h.fence = NEW.fence)) THEN RAISE(ABORT, 'writer admission is closed or fenced') END;

END;

CREATE TRIGGER IF NOT EXISTS artifact_storage_events_insert_guard BEFORE INSERT ON artifact_storage_events
BEGIN
    SELECT CASE WHEN NEW.predecessor_id IS NULL AND (NEW.kind != 'sealed' OR EXISTS (SELECT 1 FROM artifact_storage_events WHERE artifact_id = NEW.artifact_id)) THEN RAISE(ABORT, 'invalid storage root') END;
    SELECT CASE WHEN NEW.predecessor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM artifact_storage_events p WHERE p.event_id = NEW.predecessor_id AND p.artifact_id = NEW.artifact_id AND p.kind != NEW.kind) THEN RAISE(ABORT, 'invalid storage transition') END;
    SELECT CASE WHEN NEW.kind = 'gc_deleted' AND (EXISTS (SELECT 1 FROM (SELECT h.* FROM artifact_holder_events h WHERE h.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_holder_events n WHERE n.predecessor_id = h.event_id)) h WHERE h.artifact_id = NEW.artifact_id)
      OR EXISTS (SELECT 1 FROM (SELECT c.* FROM artifact_writer_claims c WHERE c.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims n WHERE n.predecessor_id = c.event_id)) c WHERE c.artifact_id = NEW.artifact_id)) THEN RAISE(ABORT, 'GC cannot delete held content or live writers') END;
    SELECT CASE WHEN NEW.kind = 'sealed' AND NOT EXISTS (SELECT 1 FROM (SELECT c.* FROM artifact_writer_claims c WHERE c.event_kind = 'acquire' AND NOT EXISTS (SELECT 1 FROM artifact_writer_claims n WHERE n.predecessor_id = c.event_id)) c JOIN publication_operation_events o ON o.operation_id = c.operation_id
      JOIN artifact_lease_events l ON l.operation_id = c.operation_id
      WHERE c.artifact_id = NEW.artifact_id AND c.fence = o.fence AND o.phase = 'preparing' AND l.fence = c.fence AND l.admission_open = 1
        AND NOT EXISTS (SELECT 1 FROM publication_operation_events n WHERE n.predecessor_id = o.event_id)
        AND NOT EXISTS (SELECT 1 FROM artifact_lease_events n WHERE n.predecessor_id = l.event_id)) THEN RAISE(ABORT, 'seal requires a live admitted fenced writer') END;

END;
