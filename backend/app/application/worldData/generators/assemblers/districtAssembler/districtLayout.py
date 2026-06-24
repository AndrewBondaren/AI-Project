from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.db.models.mapCell import MapCell


@dataclass
class DistrictLayout:
    """
    Результат сборки района DistrictAssembler.

    area_layouts  — собранные участки (здания + дворы + заборы).
    street_cells  — ячейки внутренних улиц района; зарезервировано,
                    механика дорог не описана в ТЗ.
    barrier_cells — заборы / стены на уровне района (не здания).
    """
    area_layouts:  list[AreaLayout]
    street_cells:  list[MapCell]   = field(default_factory=list)
    barrier_cells: list[MapCell]   = field(default_factory=list)
