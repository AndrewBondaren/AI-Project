from dataclasses import dataclass, field

from app.dataModel.spatial.facing import Facing


@dataclass
class AreaSlot:
    """
    Участок, выделенный DistrictAssembler под одно здание.

    cells    — (x, y) координаты участка без z; покрывает здание + двор + забор.
    ground_z — уровень земли для этого участка (из terrain).
    facing   — какая сторона участка смотрит на улицу; определяет ориентацию
               главного входа здания и воротного проёма в заборе.
    """
    cells:    list[tuple[int, int]]
    ground_z: int
    facing:   Facing
