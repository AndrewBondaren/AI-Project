from dataclasses import dataclass

from app.db.mapper import bool_col, json_col, json_nullable_col


@dataclass
class Npc:
    __table__          = "character_sheet"
    __pk__             = "character_uid"
    __discriminator__  = {"character_type": "npc"}
    __update_exclude__ = frozenset({"world_uid"})

    character_uid:              str
    display_name:               str 
    world_uid:                   str
    created_at:                 str

    # identification
    system_class:               str | None = None
    display_class:              str | None = None
    system_gender:              str | None = None
    display_gender:             str | None = None
    system_race:                str | None = None
    display_race:               str | None = None
    system_nickname:            str | None = None
    display_nickname:           str | None = None
    system_reputation:          str | None = None
    display_reputation:         str | None = None
    system_social_status:       str | None = None
    display_social_status:      str | None = None
    system_age_type:            str | None = None
    display_age_type:           str | None = None
    system_title:               str | None = None
    display_title:              str | None = None

    # location
    system_location:            str | None = None
    display_location:           str | None = None

    # money
    system_money:               dict = json_col(default_factory=dict)
    display_money:              dict = json_col(default_factory=dict)

    # vitals
    system_alive:               bool = bool_col(default=True)
    system_conscious:           bool = bool_col(default=True)
    system_barrier:             str | None = None
    display_barrier:            str | None = None

    # stats
    system_stats:               dict = json_col(default_factory=dict)
    display_stats:              dict = json_col(default_factory=dict)

    # narrative
    system_description:         str | None = None
    display_description:        str | None = None
    system_character:           str | None = None
    display_character:          str | None = None
    system_appearance:          str | None = None
    display_appearance:         str | None = None
    character_traits_dirty:     bool = bool_col(default=False)
    system_birthday:            str | None = None
    display_birthday:           str | None = None
    system_origin:              str | None = None
    display_origin:             str | None = None
    system_motivation:          str | None = None
    display_motivation:         str | None = None
    system_background:          str | None = None
    display_background:         str | None = None

    # faction
    system_faction_uid:         str | None = None
    system_faction_rank:        str | None = None
    display_faction_rank:       str | None = None

    # spawn / respawn
    home_location_uid:          str | None = None
    work_location_uid:          str | None = None
    spawn_location_uid:         str | None = None
    can_respawn:                bool = bool_col(default=False)
    respawn_after_ticks:        int | None = None
    system_respawn_place_type:  str | None = None
    respawn_location_uid:       str | None = None

    # engine fields
    system_current_needs:       dict       = json_col(default_factory=dict)
    system_current_target:      dict | None = json_nullable_col()
    system_npc_goal:            dict | None = json_nullable_col()
    system_current_thoughts:    str | None = None
    display_current_thoughts:   str | None = None

    world_schema_version:       str | None = None
