from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell


@dataclass
class DistrictLayout:
    """
    Результат сборки района DistrictAssembler.

    area_layouts      — собранные участки (здания + дворы + заборы).
    connection_nodes  — узлы графа дорог уровня "district".
    connection_edges  — рёбра графа дорог уровня "district".
    barrier_cells     — заборы / стены на уровне района (не здания).
    """
    area_layouts:     list[AreaLayout]
    connection_nodes: list[ConnectionNode] = field(default_factory=list)
    connection_edges: list[ConnectionEdge] = field(default_factory=list)
    barrier_cells:    list[MapCell]        = field(default_factory=list)
