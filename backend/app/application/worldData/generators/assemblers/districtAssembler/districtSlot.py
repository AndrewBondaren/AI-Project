from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import ConnectionEntry


@dataclass
class DistrictSlot:
    """
    Позиция размещённого шаблона района.

    Создаётся SettlementAssembler после проверки placement_conditions шаблона.
    district_template — уже выбранный шаблон; условия гарантированно выполнены.

    Координаты в WORLD_LOCAL_METERS — вычислены SettlementAssembler из:
        origin = settlement_origin_m(settlement)
        (origin_x, origin_y) = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_size_m(world))

    entry_nodes — точки входа/выхода на гранях района, созданные SettlementAssembler.
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
    required_structures: list[dict] = field(default_factory=list)  # tz_city_generation §9.4
