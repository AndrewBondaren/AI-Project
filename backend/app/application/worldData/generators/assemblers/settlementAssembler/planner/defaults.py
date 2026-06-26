"""Built-in district templates when world has no district_template_registry."""

from enum import StrEnum

#TODO more default district templates
DEFAULT_DISTRICT_TEMPLATES: list[dict] = [
    {
        "system_name":           "civic_center",
        "display_name":          "Центральный квартал",
        "district_type":         "civic",
        "placement_conditions":  [{"type": "min_city_size", "size": "town"}],
        "max_per_city":          1,
        "street_layout":         "grid",
        "connections":           [{"connection_type": "road", "role": "main_street", "sidewalk": True}],
    },
    {
        "system_name":           "commercial_quarter",
        "display_name":          "Торговый квартал",
        "district_type":         "commercial",
        "placement_conditions":  [],
        "street_layout":         "grid",
        "connections":           [{"connection_type": "road", "role": "main_street", "sidewalk": True}],
    },
    {
        "system_name":           "residential_quarter",
        "display_name":          "Жилой квартал",
        "district_type":         "residential",
        "placement_conditions":  [],
        "street_layout":         "grid",
        "connections":           [{"connection_type": "road", "role": "main_street", "sidewalk": True}],
    },
    {
        "system_name":           "industrial_quarter",
        "display_name":          "Промышленный квартал",
        "district_type":         "industrial",
        "placement_conditions":  [{"type": "min_city_size", "size": "town"}],
        "street_layout":         "grid",
        "connections":           [{"connection_type": "road", "role": "service_road", "sidewalk": False}],
    },
    {
        "system_name":           "port_district",
        "display_name":          "Портовый район",
        "district_type":         "port",
        "placement_conditions":  [
            {"type": "adjacent_terrain", "terrain_types": ["liquid_body"], "min_count": 1},
            {"type": "min_city_size", "size": "town"},
        ],
        "max_per_city":          1,
        "street_layout":         "grid",
        "density":               "dense",
        "connections":           [{"connection_type": "road", "role": "main_street", "sidewalk": True}],
    },
]

DEFAULT_FOOTPRINT_MULTIPLIER: dict[str, float] = {
    "hamlet":      0.25,
    "village":     0.5,
    "town":        1.0,
    "city":        2.0,
    "metropolis":  4.0,
    "megalopolis": 4.0,
}

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
    CellZone.EDGE:   ("commercial", "residential", "industrial", "port"),
    CellZone.INNER:  ("residential", "commercial", "industrial"),
}
