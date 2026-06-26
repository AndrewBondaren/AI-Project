"""Minimal building templates for settlement smoke tests (when world registry is empty)."""

DEFAULT_BUILDING_TEMPLATES: list[dict] = [
    {
        "system_name":         "town_hall",
        "structure_type":      "building",
        "display_name":        "Ратуша",
        "default_z_height":    3,
        "economic_tier_range": {"min": "basic", "max": "exceptional"},
        "default_structure_context": {
            "foundation_type": "slab",
            "roof_type":       "gable",
        },
        "perimeter_barrier": {"template": "stone_fence", "probability": 1.0},
        "levels": [
            {
                "z_offset":     0,
                "display_name": "Первый этаж",
                "rooms": [
                    {
                        "room_id":      "hall",
                        "room_type":    "common_hall",
                        "display_name": "Зал",
                        "shape_type":   "square",
                        "size":         {"size_type": "small"},
                        "required":     True,
                        "count":        1,
                        "is_public":    True,
                        "is_forbidden": False,
                        "entry_point": {
                            "wall":         "south",
                            "passage_type": "main_entrance",
                        },
                    },
                ],
            },
        ],
    },
    {
        "system_name":         "inn_small",
        "structure_type":      "building",
        "display_name":        "Таверна",
        "default_z_height":    3,
        "economic_tier_range": {"min": "basic", "max": "quality"},
        "default_structure_context": {
            "foundation_type": "slab",
            "roof_type":       "gable",
        },
        "levels": [
            {
                "z_offset":     0,
                "display_name": "Первый этаж",
                "rooms": [
                    {
                        "room_id":      "taproom",
                        "room_type":    "common_hall",
                        "display_name": "Зал",
                        "shape_type":   "square",
                        "size":         {"size_type": "small"},
                        "required":     True,
                        "count":        1,
                        "is_public":    True,
                        "is_forbidden": False,
                        "entry_point": {
                            "wall":         "south",
                            "passage_type": "main_entrance",
                        },
                    },
                ],
            },
        ],
    },
]

DEFAULT_ECONOMIC_TIER_REGISTRY: list[dict] = [
    {"system_tier": "poor",        "display_tier": "Poor",        "base_value": 0},
    {"system_tier": "basic",       "display_tier": "Basic",       "base_value": 1},
    {"system_tier": "standard",    "display_tier": "Standard",    "base_value": 10},
    {"system_tier": "quality",     "display_tier": "Quality",     "base_value": 100},
    {"system_tier": "premium",     "display_tier": "Premium",     "base_value": 500},
    {"system_tier": "exceptional", "display_tier": "Exceptional", "base_value": 2000},
]


def merge_building_registry(world) -> list[dict]:
    """World registry + defaults (world wins on name collision)."""
    by_name: dict[str, dict] = {t["system_name"]: t for t in DEFAULT_BUILDING_TEMPLATES}
    for t in world.building_template_registry or []:
        by_name[t["system_name"]] = t
    return list(by_name.values())


def lookup_building_template(world, system_name: str) -> dict | None:
    for t in merge_building_registry(world):
        if t.get("system_name") == system_name:
            return t
    return None
