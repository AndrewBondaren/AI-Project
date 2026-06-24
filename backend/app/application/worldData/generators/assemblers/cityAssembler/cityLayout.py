from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.db.models.mapCell import MapCell


@dataclass
class CityLayout:
    """
    Результат сборки поселения CityAssembler.

    district_layouts — собранные районы города.
    road_cells       — ячейки главных магистралей и улиц поселения.
    barrier_cells    — ячейки городских стен и укреплений.

    Открытые вопросы:
      - Многоуровневая топология (наземный / подземный / воздушный город) — нет ТЗ.
      - Механика дорог (road_type, соединение с внешней картой) — нет ТЗ.
    """
    district_layouts: list[DistrictLayout]
    road_cells:       list[MapCell] = field(default_factory=list)
    barrier_cells:    list[MapCell] = field(default_factory=list)
