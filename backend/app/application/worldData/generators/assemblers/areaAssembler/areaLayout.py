from dataclasses import dataclass, field

from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation


@dataclass
class AreaLayout:
    """
    Результат сборки участка StructureAreaAssembler.

    Слои намеренно разделены — участок многоуровневый,
    мешать здание / забор / двор в одну плоскую структуру нельзя.
    """
    building_location: NamedLocation
    building_layout:   StructureLayout
    barrier_cells:     list[MapCell]          = field(default_factory=list)
    yard_cells:        list[MapCell]          = field(default_factory=list)
    small_layouts:     list[StructureLayout]  = field(default_factory=list)
