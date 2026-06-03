from dataclasses import dataclass

from app.db.mapper import bool_col, json_nullable_col


@dataclass
class NamedLocation:
    __table__          = "named_locations"
    __pk__             = "location_uid"
    __update_exclude__ = frozenset({"world_uid"})

    location_uid:               str
    world_uid:                   str
    display_name:               str
    system_location_type:       str
    created_at:                 str

    parent_location_uid:        str | None = None
    system_location_subtype:    str | None = None
    system_description:         str | None = None
    display_description:        str | None = None
    glossary_ref:               str | None = None
    tag_refs:                   list | None = json_nullable_col()
    is_discovered:              bool = bool_col(default=False)
    is_accessible:              bool = bool_col(default=True)
    entry_difficulty:           int | None = None
    guard_level:                int | None = None
    system_location_mood:       str | None = None
    display_location_mood:      str | None = None
    owner_uid:                  str | None = None
    system_climate_zone:        str | None = None
    state_uid:                  str | None = None
    system_city_size:           str | None = None
    system_economic_tier:       str | None = None
    is_public:                  bool = bool_col(default=False)
    is_forbidden:               bool = bool_col(default=False)
    is_selectable:              bool = bool_col(default=True)
    map_x:                      int | None = None
    map_y:                      int | None = None
    map_z:                      int | None = None
    is_mobile:                  bool = bool_col(default=False)
