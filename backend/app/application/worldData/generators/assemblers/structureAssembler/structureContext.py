from dataclasses import dataclass

from app.dataModel.spatial.facing import Facing


@dataclass
class StructureContext:
    foundation_type:     str               # "none"|"slab"|"perimeter"|"full"|"hull"
    roof_type:           str | list[str]   # "none"|"flat"|"gable"|"hull" or priority list
    facing:              Facing | None = None  # направление главного входа; None → определяется шаблоном
    foundation_depth:    int   = 1
    slope_step:          float = 1.0       # footprint shrink per z-unit for sloped roofs
    foundation_material: str | None = None
    roof_material:       str | None = None
    porch_material:      str | None = None
    porch_has_roof:      bool = False
    ground_z:            int | None = None  # None → resolved from building.map_z
