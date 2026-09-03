"""Engine builtin building layout bodies — used when world registry has no layout rows.

Nested level/room dicts — **POJO-D-16** / JV-4b; after nested models, construct from POJO not wire dicts.
"""

from __future__ import annotations

from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.shared.ranges import EconomicTierRange
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate

_TOWN_HALL_LEVELS: list[dict] = [
    {
        "z_offset": 0,
        "display_name": "Первый этаж",
        "rooms": [
            {
                "room_id": "hall",
                "room_type": "common_hall",
                "display_name": "Зал",
                "shape_type": "square",
                "size": {"size_type": "small"},
                "required": True,
                "count": 1,
                "is_public": True,
                "is_forbidden": False,
                "entry_point": {
                    "wall": "south",
                    "passage_type": "main_entrance",
                },
            },
        ],
    },
]

_INN_LEVELS: list[dict] = [
    {
        "z_offset": 0,
        "display_name": "Первый этаж",
        "rooms": [
            {
                "room_id": "taproom",
                "room_type": "common_hall",
                "display_name": "Зал",
                "shape_type": "square",
                "size": {"size_type": "small"},
                "required": True,
                "count": 1,
                "is_public": True,
                "is_forbidden": False,
                "entry_point": {
                    "wall": "south",
                    "passage_type": "main_entrance",
                },
            },
        ],
    },
]

_CANONICAL_LAYOUTS: tuple[BuildingLayoutTemplate, ...] = (
    BuildingLayoutTemplate(
        system_name="town_hall",
        structure_type="building",
        display_name="Ратуша",
        economic_tier_range=EconomicTierRange(min="basic", max="exceptional"),
        perimeter_barrier=PerimeterBarrier(template="stone_fence", probability=1.0),
        levels=_TOWN_HALL_LEVELS,
    ),
    BuildingLayoutTemplate(
        system_name="inn_small",
        structure_type="building",
        display_name="Таверна",
        economic_tier_range=EconomicTierRange(min="basic", max="quality"),
        levels=_INN_LEVELS,
    ),
)


def canonical_defaults() -> list[BuildingLayoutTemplate]:
    """Builtin layout catalog merged under world layout-shaped rows."""
    return list(_CANONICAL_LAYOUTS)
