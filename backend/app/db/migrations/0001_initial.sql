CREATE TABLE IF NOT EXISTS worlds (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    narrative_language  TEXT NOT NULL DEFAULT 'ru',
    measurement_system  TEXT NOT NULL DEFAULT 'metric',
    current_tick        INTEGER NOT NULL DEFAULT 0,
    stat_schema         TEXT,
    skill_schema        TEXT,
    combat_settings     TEXT,
    calendar            TEXT,
    schema_version      TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_sheet (
    character_uid        TEXT PRIMARY KEY,
    character_type       TEXT NOT NULL,
    display_name         TEXT NOT NULL,
    system_alive         INTEGER NOT NULL DEFAULT 1,
    system_conscious     INTEGER NOT NULL DEFAULT 1,
    system_race          TEXT,
    system_location      TEXT,
    system_stats         TEXT,
    world_id             TEXT,
    world_schema_version TEXT,
    system_current_needs     TEXT,
    system_current_target    TEXT,
    system_npc_goal          TEXT,
    system_current_thoughts  TEXT,
    display_current_thoughts TEXT,
    created_at           TEXT NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id)
);

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

CREATE TABLE IF NOT EXISTS scene_participants (
    session_id    TEXT NOT NULL,
    character_uid TEXT NOT NULL,
    PRIMARY KEY (session_id, character_uid),
    FOREIGN KEY (session_id)    REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (character_uid) REFERENCES character_sheet(character_uid)
);

CREATE TABLE IF NOT EXISTS messages (
    message_id   TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    player_input TEXT,
    llm_output   TEXT,
    game_tick    INTEGER,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id)
);
