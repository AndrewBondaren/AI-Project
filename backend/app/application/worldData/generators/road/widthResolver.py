"""
Вычисляет width_cells для ConnectionEdge по типу дороги и количеству полос.
Правила — см. tz_structure_connections.md §3.4.
"""

# Типы с фиксированной шириной независимо от lanes_per_side
_FIXED: dict[str, int | None] = {
    "trail":           1,
    "dirt_road":       2,
    "alley":           2,
    "yard_path":       1,
    "portal":          None,   # нет физических ячеек
    "air_route":       None,
    "sea_route":       None,
}

# Ширина одной полосы в клетках для типов с lane-логикой
_LANE_WIDTH = 2   # road, highway: 2 клетки на полосу


def resolve_width(
    connection_type: str,
    lanes_per_side:  int  = 1,
    bidirectional:   bool = True,
) -> int | None:
    """
    Возвращает ширину ребра в клетках.
    None — у типов без физических ячеек (portal, air_route, sea_route).

    settlement_gate наследует ширину продолжающегося ребра — резолв выполняется
    на уровне CityAssembler, не здесь.
    """
    if connection_type in _FIXED:
        return _FIXED[connection_type]

    if connection_type in ("road", "highway"):
        one_side = lanes_per_side * _LANE_WIDTH
        return one_side * 2 if bidirectional else one_side

    # bridge — ширина определяется bridge_subtype; fallback = как road
    if connection_type == "bridge":
        one_side = lanes_per_side * _LANE_WIDTH
        return one_side * 2 if bidirectional else one_side

    # кастомный тип — fallback: 2 клетки
    return 2
