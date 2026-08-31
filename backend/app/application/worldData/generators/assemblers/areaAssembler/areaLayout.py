from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import AreaThreshold
from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import StreetApproach
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation


@dataclass
class AreaLayout:
    """
    Результат сборки участка StructureAreaAssembler.

    Слои намеренно разделены — участок многоуровневый,
    мешать здание / забор / двор в одну плоскую структуру нельзя.
    slot — геометрия участка для extract (area uid / facing); assembler не ходит в SQL.
    Здание не обязательно (двор / забор / площадка).
    """
    slot:              AreaSlot
    threshold:         AreaThreshold
    approach:          StreetApproach | None = None
    building_location: NamedLocation | None = None
    building_layout:   StructureLayout | None = None
    barrier_cells:     list[MapCell]          = field(default_factory=list)
    yard_cells:        list[MapCell]          = field(default_factory=list)
    small_layouts:     list[StructureLayout]  = field(default_factory=list)
    connection_nodes:  list[ConnectionNode]   = field(default_factory=list)
    connection_edges:  list[ConnectionEdge]   = field(default_factory=list)
