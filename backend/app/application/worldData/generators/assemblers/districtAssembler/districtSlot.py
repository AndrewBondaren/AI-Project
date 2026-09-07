"""DistrictSlot — placed district template on settlement grid."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import ConnectionEntry
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.requiredStructure import RequiredStructure


@dataclass
class DistrictSlot:
    """
    Позиция размещённого шаблона района.

    Создаётся SettlementAssembler после проверки placement_conditions шаблона.
    district_template — уже выбранный шаблон; условия гарантированно выполнены.

    Координаты в WORLD_FINE_GRID — вычислены SettlementAssembler из:
        origin = settlement_origin_fine(settlement)
        (origin_x, origin_y) = coarse_cell_fine_xy(origin, cell_x, cell_y, map_cell_fine_span(world))

    width_fine / depth_fine — сторона слота в fine-клетках (не coarse).
    Полная глобальная клетка: width_fine = depth_fine = map_cell_fine_span(world).

    entry_nodes — точки входа/выхода на гранях района, созданные SettlementAssembler.
    DistrictAssembler прокладывает through_road-коридоры от этих точек,
    затем строит внутреннюю сетку вокруг них.
    """
    origin_x:            int
    origin_y:            int
    width_fine:          int
    depth_fine:          int
    ground_z:            int
    district_template:   DistrictTemplateEntry
    entry_nodes:         list[ConnectionEntry] = field(default_factory=list)
    required_structures: list[RequiredStructure] = field(default_factory=list)
    cell_x:              int = 0
    cell_y:              int = 0
    # structure_type → subjects of this settlement that apply to that type (not wire).
    subject_tags:        dict[str, tuple[str, ...]] = field(default_factory=dict)
