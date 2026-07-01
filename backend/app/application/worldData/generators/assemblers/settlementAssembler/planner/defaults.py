"""Built-in district templates when world has no district_template_registry."""

from enum import StrEnum

#TODO more default district templates

CITY_SIZE_ORDER: list[str] = [
    "hamlet", "village", "town", "city", "metropolis", "megalopolis",
]


class CellZone(StrEnum):
    """Позиция глобальной ячейки в сетке footprint."""
    CENTER = "center"
    EDGE   = "edge"
    INNER  = "inner"


DISTRICT_TYPE_PREFERENCE: dict[CellZone, tuple[str, ...]] = {
    CellZone.CENTER: ("civic", "commercial", "residential"),
    CellZone.EDGE:   ("port", "commercial", "residential", "industrial"),
    CellZone.INNER:  ("residential", "commercial", "industrial"),
}
