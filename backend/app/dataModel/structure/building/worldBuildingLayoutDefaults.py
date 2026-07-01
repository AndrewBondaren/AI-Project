"""Engine builtin building layout bodies — used when world registry is empty."""

from __future__ import annotations

_CANONICAL_LAYOUTS: tuple[dict, ...] = (
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
)


def canonical_defaults() -> list[dict]:
    """Builtin layout catalog merged under world.building_template_registry rows."""
    return [dict(layout) for layout in _CANONICAL_LAYOUTS]
