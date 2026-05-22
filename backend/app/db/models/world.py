from dataclasses import dataclass

from app.db.mapper import bool_col, json_col, json_nullable_col


@dataclass
class World:
    __table__ = "worlds"
    __pk__    = "id"

    id:                         str
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

    # custom field declarations
    player_fields:              dict = json_col(default_factory=dict)
    npc_fields:                 dict = json_col(default_factory=dict)

    # migration
    stat_conflict_mode:         str  = "soft"
    stat_migrations:            dict = json_col(default_factory=dict)
    registry_migrations:        dict = json_col(default_factory=dict)
    trait_change_log_threshold: float = 0.2
