PRAGMA auto_vacuum = INCREMENTAL;

-- ============================================================
-- worlds
-- ============================================================
CREATE TABLE IF NOT EXISTS worlds (
    id                          TEXT PRIMARY KEY,
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
    world_id      TEXT NOT NULL,
    display_race  TEXT NOT NULL,
    race_traits   TEXT,
    male          TEXT,
    female        TEXT,
    asexual       TEXT,
    both          TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id)
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
    system_race             TEXT REFERENCES races(race_uid),
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

    -- spawn / respawn (NPC only)
    home_location_uid       TEXT,
    work_location_uid       TEXT,
    spawn_location_uid      TEXT,
    can_respawn             INTEGER NOT NULL DEFAULT 0,
    respawn_after_ticks     INTEGER,
    system_respawn_place_type TEXT,
    respawn_location_uid    TEXT,

    -- NPC engine fields
    system_current_needs    TEXT,
    system_current_target   TEXT,
    system_npc_goal         TEXT,
    system_current_thoughts TEXT,
    display_current_thoughts TEXT,

    -- world binding
    world_id                TEXT,
    world_schema_version    TEXT,

    created_at              TEXT NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id)
);

-- ============================================================
-- game_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS game_sessions (
    id                        TEXT PRIMARY KEY,
    world_id                  TEXT NOT NULL,
    player_character_id       TEXT NOT NULL,
    restored_from_snapshot_id TEXT,
    created_at                TEXT NOT NULL,
    last_active_at            TEXT NOT NULL,
    UNIQUE (world_id, player_character_id),
    FOREIGN KEY (world_id)            REFERENCES worlds(id),
    FOREIGN KEY (player_character_id) REFERENCES character_sheet(character_uid)
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
-- messages
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id   TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    player_input TEXT,
    llm_output   TEXT,
    game_tick    INTEGER,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id)
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
-- character_perks  (common perks — uid ref + rank)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_perks (
    character_id  TEXT NOT NULL,
    perk_uid      TEXT NOT NULL,
    current_rank  TEXT,
    PRIMARY KEY (character_id, perk_uid),
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
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
    FOREIGN KEY (character_id) REFERENCES character_sheet(character_uid) ON DELETE CASCADE
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
    world_id       TEXT NOT NULL,
    source_uid     TEXT NOT NULL,
    target_uid     TEXT NOT NULL,
    relation_data  TEXT,
    PRIMARY KEY (world_id, source_uid, target_uid),
    FOREIGN KEY (world_id) REFERENCES worlds(id)
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
    world_id     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id)
);

CREATE TABLE IF NOT EXISTS world_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    timeline_id        TEXT NOT NULL,
    world_id           TEXT NOT NULL,
    turn_id            INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    parent_snapshot_id TEXT,
    snapshot_data      BLOB NOT NULL,
    snapshot_checksum  TEXT NOT NULL,
    FOREIGN KEY (timeline_id)        REFERENCES timelines(timeline_id),
    FOREIGN KEY (world_id)           REFERENCES worlds(id),
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
    FOREIGN KEY (session_id) REFERENCES game_sessions(id)
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
-- indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_character_sheet_world    ON character_sheet (world_id);
CREATE INDEX IF NOT EXISTS idx_character_sheet_location ON character_sheet (system_location);
CREATE INDEX IF NOT EXISTS idx_character_sheet_type     ON character_sheet (character_type);

CREATE INDEX IF NOT EXISTS idx_messages_session         ON messages (session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_game_sessions_world      ON game_sessions (world_id);

CREATE INDEX IF NOT EXISTS idx_character_history_char   ON character_history (character_id);
CREATE INDEX IF NOT EXISTS idx_character_wounds_char    ON character_wounds (character_id);
CREATE INDEX IF NOT EXISTS idx_npc_thoughts_char        ON npc_thoughts_about (character_id);

CREATE INDEX IF NOT EXISTS idx_world_relations_source   ON world_relations (world_id, source_uid);
CREATE INDEX IF NOT EXISTS idx_world_relations_target   ON world_relations (world_id, target_uid);

CREATE INDEX IF NOT EXISTS idx_registry_deps_lookup     ON registry_dependencies (registry_type, registry_key);
CREATE INDEX IF NOT EXISTS idx_registry_deps_entity     ON registry_dependencies (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_timeline       ON world_snapshots (timeline_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_parent         ON world_snapshots (parent_snapshot_id);
