from collections.abc import Iterable
from dataclasses import dataclass

from app.dataModel.spatial.facing import Facing


@dataclass
class AreaSlot:
    """
    Участок, выделенный DistrictAssembler под одно здание.

    cells    — (x, y) координаты участка без z; покрывает здание + двор + забор.
    ground_z — уровень земли для этого участка (из terrain; финал — assembler).
    facing   — какая сторона участка смотрит на улицу; определяет ориентацию
               главного входа здания и воротного проёма в заборе.
    height   — вертикальный пролёт выше ground_z (fine cells): сумма z_height
               этажей, которые выступают над землёй. Packing = 0; финал —
               StructureAreaAssembler по levels здания.
    z_deep   — то же ниже ground_z (подвал). Плоскость ground_z не входит:
               [z, ground_z) vs [ground_z, top). Packing = 0.
    deck     — копия яруса чертежа района (`DistrictTemplateEntry.deck`).
               SoT — настройка района, не участок. 0 = поверхность.
               Не этаж здания и не economic tier. Коллизия xy×z только если
               среди участков района больше одного яруса.
    """
    cells:    list[tuple[int, int]]
    ground_z: int
    facing:   Facing
    height:   int = 0
    z_deep:   int = 0
    deck:     int = 0


SURFACE_DECK = 0


def z_range(slot: AreaSlot) -> tuple[int, int]:
    """Half-open fine-z interval ``[ground_z - z_deep, ground_z + height)``."""
    return slot.ground_z - slot.z_deep, slot.ground_z + slot.height


def _level_span(level: object) -> tuple[int, int]:
    z = int(getattr(level, "z"))
    z_height = int(getattr(level, "z_height"))
    return z, z + z_height


def height_from_levels(ground_z: int, levels: Iterable[object]) -> int:
    """Sum of each floor's span in ``[ground_z, top)``."""
    total = 0
    for level in levels:
        z, top = _level_span(level)
        total += max(0, top - max(z, ground_z))
    return total


def z_deep_from_levels(ground_z: int, levels: Iterable[object]) -> int:
    """Sum of each floor's span in ``[z, ground_z)``. Does not include ``ground_z``."""
    total = 0
    for level in levels:
        z, top = _level_span(level)
        total += max(0, min(top, ground_z) - z)
    return total
