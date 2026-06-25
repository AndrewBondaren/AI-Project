from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell


@dataclass
class CityLayout:
    """
    Результат сборки поселения CityAssembler.

    district_layouts  — собранные районы города.
    connection_nodes  — узлы графа дорог уровня "city" (settlement_gate, межрайонные пересечения).
    connection_edges  — рёбра графа дорог уровня "city".
    barrier_cells     — ячейки городских стен и укреплений.
    """
    district_layouts:  list[DistrictLayout]
    connection_nodes:  list[ConnectionNode] = field(default_factory=list)
    connection_edges:  list[ConnectionEdge] = field(default_factory=list)
    barrier_cells:     list[MapCell]        = field(default_factory=list)
