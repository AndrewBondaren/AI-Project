"""Engine builtin plot drawings — packing catalog when world registry has no layout rows.

``inn_small`` is the plot example: envelope + nested building from
``fixtures/templates/tavern_1.json`` (same body as ``fixtures/templates/inn_small.json``).

Nested level/room dicts — **POJO-D-16** / JV-4b; after nested models, construct from POJO not wire dicts.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.shared.ranges import EconomicTierRange
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.building.occupiedFootprint import OccupiedFootprintSpec

_FIXTURES_TEMPLATES = (
    Path(__file__).resolve().parents[5] / "fixtures" / "templates"
)

_STUB_FOOTPRINT = OccupiedFootprintSpec(width=4, depth=4)

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


def _load_fixture_layout(stem: str) -> BuildingLayoutTemplate:
    path = _FIXTURES_TEMPLATES / f"{stem}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BuildingLayoutTemplate.model_validate(raw)


def _stub_plot(
    system_name: str,
    structure_type: str,
    display_name: str,
    *,
    resource_kind: ResourceKind | None = None,
    crop_kind: CropKind | None = None,
    perimeter_barrier: PerimeterBarrier | None = None,
) -> BuildingLayoutTemplate:
    kwargs: dict = {}
    if resource_kind is not None:
        kwargs["resource_kind"] = resource_kind
    if crop_kind is not None:
        kwargs["crop_kind"] = crop_kind
    if perimeter_barrier is not None:
        kwargs["perimeter_barrier"] = perimeter_barrier
    return BuildingLayoutTemplate(
        system_name=system_name,
        structure_type=structure_type,
        display_name=display_name,
        occupied_footprint=_STUB_FOOTPRINT,
        economic_tier_range=EconomicTierRange(min="basic", max="quality"),
        levels=_TOWN_HALL_LEVELS,
        **kwargs,
    )


_CANONICAL_LAYOUTS: tuple[BuildingLayoutTemplate, ...] = (
    BuildingLayoutTemplate(
        system_name="town_hall",
        structure_type="town_hall",
        display_name="Ратуша",
        occupied_footprint=_STUB_FOOTPRINT,
        economic_tier_range=EconomicTierRange(min="basic", max="exceptional"),
        perimeter_barrier=PerimeterBarrier(template="stone_fence", probability=1.0),
        levels=_TOWN_HALL_LEVELS,
    ),
    _load_fixture_layout("inn_small"),
    _stub_plot("mine", "mine", "Шахта", resource_kind=ResourceKind.ORE),
    _stub_plot("mill", "mill", "Мельница"),
    _stub_plot("smelter", "smelter", "Плавильня"),
    _stub_plot("workshop", "workshop", "Мастерская"),
    _stub_plot("temple", "temple", "Храм"),
    _stub_plot("theater", "theater", "Театр"),
    _stub_plot("library", "library", "Библиотека"),
    _stub_plot("farm", "farm", "Ферма", crop_kind=CropKind.GRAIN),
    _stub_plot("livestock", "livestock", "Загон"),
)


def canonical_defaults() -> list[BuildingLayoutTemplate]:
    """Builtin plot catalog merged under world layout-shaped rows."""
    return list(_CANONICAL_LAYOUTS)
