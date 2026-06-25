from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import ConnectionEntry


@dataclass
class DistrictSlot:
    """
    Позиция размещённого шаблона района.

    Создаётся CityAssembler после проверки placement_conditions шаблона.
    district_template — уже выбранный шаблон; условия гарантированно выполнены.

    Координаты в мировых метрах — вычислены CityAssembler из:
        origin_x = cell_x * cell_size_m + offset
        cell_size_m = world.map_cell_size_m

    entry_nodes — точки входа/выхода на гранях района, созданные CityAssembler.
    DistrictAssembler прокладывает through_road-коридоры от этих точек,
    затем строит внутреннюю сетку вокруг них.
    """
    origin_x:          int
    origin_y:          int
    width_m:           int
    depth_m:           int
    ground_z:          int
    district_template: dict                      # выбранный шаблон; placement_conditions проверены
    entry_nodes:       list[ConnectionEntry] = field(default_factory=list)
