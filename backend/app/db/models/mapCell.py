from dataclasses import dataclass

from app.db.mapper import bool_col, json_nullable_col


@dataclass
class MapCell:
    __table__ = "map_cells"
    __pk__    = "world_uid"  # composite PK (world_uid, x, y, z) — используется только upsert

    world_uid:                  str
    x:                          int
    y:                          int
    z:                          int

    system_terrain:             str | None = None   # тип рельефа из terrain_registry (plains, tundra, forest, liquid_body, urban, road, floor, wall, ...)
    system_building_element:   str | None = None   # строительный элемент (wall, floor, door, window, ...)

    system_material:                str | None = None
    is_structural:                  bool = bool_col(default=False)
    travel_modifier_override:       float | None = None
    system_danger_level_override:   str | None = None
    gap_width_override:         int | None = None
    temperature_base:           int | None = None
    rainfall:                   int | None = None
    location_uid:               str | None = None
    railing_sides:              list[str] | None = json_nullable_col(default=None)  # JSON array of faces: ["N"], ["E","N"], etc.
    system_facing:              str | None = None   # cardinal direction this cell faces/moves toward (north/south/east/west)
    display_facing:             str | None = None   # localised label for system_facing ("север", "к выходу", …)
    glass_material:             str | None = None   # filling material for openings (glass, stained_glass, iron_mesh, …); None = open slit
    hydrology:                  dict | None = json_nullable_col(default=None)  # roles, liquid_candidate — tz_terrain_hydrology.md C2
