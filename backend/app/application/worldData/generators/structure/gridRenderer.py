"""
ASCII-визуализация уровня здания.
Используется в debug API и скриптах разработки.
"""
from app.db.models.mapCell import MapCell

_SYMBOLS: dict[str, str] = {
    "wall":           "#",
    "floor":          ".",
    "door":           "D",
    "stair_floor":    "_",
    "staircase_base": "B",
    "void":           " ",
    "window":         "W",
    "column":         "C",
    "railing":        "r",
    "trapdoor":       "T",
    "ladder":         "H",
    "archway":        "'",
}

_FACING_ARROW: dict[str, str] = {
    "north": "↑", "south": "↓", "east": "→", "west": "←",
}

_STAIR_ELEMENTS = {"staircase", "stair_anchor"}


def _cell_symbol(cell: MapCell) -> str:
    elem = cell.system_building_element
    if elem in _STAIR_ELEMENTS:
        if not cell.system_facing:
            raise ValueError(
                f"stair cell ({cell.x},{cell.y},z={cell.z}) "
                f"element={elem!r} has no system_facing"
            )
        return _FACING_ARROW[cell.system_facing]
    if cell.railing_sides:
        return cell.railing_sides[0].lower() if len(cell.railing_sides) == 1 else "r"
    return _SYMBOLS.get(elem, "?")


def render_level(
    cells: list[MapCell],
    z_target: int,
    anchor_dirs: dict[tuple[int, int], str] | None = None,
) -> str:
    """
    Возвращает ASCII-сетку уровня z=z_target.
    Y убывает сверху вниз (север вверху).
    anchor_dirs: (x,y) → '↑'/'↓'/'↕' — якоря лестниц с направлением (passage endpoints).
    Пустая строка если ячеек на этом z нет.
    """
    level_cells = {(c.x, c.y): c for c in cells if c.z == z_target}
    if not level_cells:
        return ""

    anchor_dirs = anchor_dirs or {}
    xs = [x for (x, _) in level_cells]
    ys = [y for (_, y) in level_cells]
    x0, x1 = min(xs) - 1, max(xs) + 1
    y0, y1 = min(ys) - 1, max(ys) + 1

    prefix = 6  # len("  21 |") — y-label + " |"
    lines: list[str] = [f"x: {x0}..{x1}  y: {y0}..{y1}"]

    for y in range(y1, y0 - 1, -1):
        row = "".join(
            anchor_dirs[(x, y)] if (x, y) in anchor_dirs and (x, y) in level_cells
            else _cell_symbol(level_cells[(x, y)]) if (x, y) in level_cells
            else " "
            for x in range(x0, x1 + 1)
        )
        lines.append(f"{y:4d} |{row}|")

    # X-axis labels: one row per digit position (hundreds, tens, units)
    x_range = range(x0, x1 + 1)
    max_abs = max(abs(x0), abs(x1))
    digit_rows = 3 if max_abs >= 100 else 2 if max_abs >= 10 else 1
    pad = " " * prefix
    for d in range(digit_rows):
        power = digit_rows - 1 - d
        row_label = "".join(
            str(abs(x) // (10 ** power) % 10) if x >= 0 else
            ("-" if abs(x) // (10 ** power) % 10 == 0 and d == 0 else
             str(abs(x) // (10 ** power) % 10))
            for x in x_range
        )
        lines.append(f"{pad}{row_label}")

    return "\n".join(lines)


def render_all_levels(
    cells:   list[MapCell],
    markers: dict[tuple[int, int, int], str] | None = None,
) -> dict[int, str]:
    """Возвращает словарь z → ASCII-сетка для всех z-уровней.

    markers: (x, y, z) → символ — перекрывает стандартный символ ячейки.
    """
    z_values = sorted({c.z for c in cells})
    z_markers: dict[int, dict[tuple[int, int], str]] = {}
    for (x, y, z), sym in (markers or {}).items():
        z_markers.setdefault(z, {})[x, y] = sym
    return {z: render_level(cells, z, anchor_dirs=z_markers.get(z)) for z in z_values}
