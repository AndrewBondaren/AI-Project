"""
ASCII-визуализация уровня здания.
Используется в debug API и скриптах разработки.
"""
from app.db.models.mapCell import MapCell

_SYMBOLS: dict[str, str] = {
    "wall":      "#",
    "floor":     ".",
    "door":      "D",
    "staircase": "S",
    "window":    "W",
    "column":    "C",
    "railing":   "r",
    "trapdoor":  "T",
}


def render_level(cells: list[MapCell], z_target: int) -> str:
    """
    Возвращает ASCII-сетку уровня z=z_target.
    Y убывает сверху вниз (север вверху).
    Пустая строка если ячеек на этом z нет.
    """
    level_cells = {(c.x, c.y): c for c in cells if c.z == z_target}
    if not level_cells:
        return ""

    xs = [x for (x, _) in level_cells]
    ys = [y for (_, y) in level_cells]
    x0, x1 = min(xs) - 1, max(xs) + 1
    y0, y1 = min(ys) - 1, max(ys) + 1

    lines: list[str] = [f"x: {x0}..{x1}  y: {y0}..{y1}"]

    for y in range(y1, y0 - 1, -1):
        row = "".join(
            _SYMBOLS.get(level_cells[(x, y)].system_building_element, "?")
            if (x, y) in level_cells else " "
            for x in range(x0, x1 + 1)
        )
        lines.append(f"{y:4d} |{row}|")

    return "\n".join(lines)


def render_all_levels(cells: list[MapCell]) -> dict[int, str]:
    """Возвращает словарь z → ASCII-сетка для всех z-уровней."""
    z_values = sorted({c.z for c in cells})
    return {z: render_level(cells, z) for z in z_values}
