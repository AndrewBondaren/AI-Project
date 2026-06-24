from dataclasses import dataclass


@dataclass
class DistrictSlot:
    """
    Позиция размещённого шаблона района.

    Создаётся CityAssembler после проверки placement_conditions шаблона.
    district_template — уже выбранный шаблон; условия гарантированно выполнены.

    Координаты в мировых метрах — вычислены CityAssembler из:
        origin_x = cell_x * cell_size_m + offset
        cell_size_m = world.map_settings["global_cell_size_m"]

    Открытые вопросы:
      - facing (ориентация к главной улице) — отложено.
      - Механика дорог (соединение с магистралями) — нет ТЗ.
    """
    origin_x:          int
    origin_y:          int
    width_m:           int
    depth_m:           int
    ground_z:          int
    district_template: dict   # выбранный шаблон; placement_conditions уже проверены
