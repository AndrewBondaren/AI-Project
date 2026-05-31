from dataclasses import dataclass

from app.db.mapper import bool_col


@dataclass
class MapCell:
    __table__ = "map_cells"
    __pk__    = "world_uid"  # composite PK (world_uid, x, y, z) — используется только upsert

    world_uid:                  str
    x:                          int
    y:                          int
    z:                          int
    system_terrain:             str

    cell_material:              str | None = None
    is_structural:              bool = bool_col(default=False)
    travel_modifier_override:   float | None = None
    danger_level_override:      str | None = None
    gap_width_override:         int | None = None
    temperature_base:           int | None = None
    rainfall:                   int | None = None
    location_uid:               str | None = None
