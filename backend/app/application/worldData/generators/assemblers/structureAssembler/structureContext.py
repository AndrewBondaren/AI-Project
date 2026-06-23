from dataclasses import dataclass


@dataclass
class StructureContext:
    foundation_type:     str               # "none"|"slab"|"perimeter"|"full"|"hull"
    roof_type:           str | list[str]   # "none"|"flat"|"gable"|"hull" or priority list
    foundation_depth:    int   = 1
    slope_step:          float = 1.0       # footprint shrink per z-unit for sloped roofs
    foundation_material: str | None = None
    roof_material:       str | None = None
    porch_material:      str | None = None
    porch_has_roof:      bool = False
    ground_z:            int | None = None  # None → resolved from building.map_z
