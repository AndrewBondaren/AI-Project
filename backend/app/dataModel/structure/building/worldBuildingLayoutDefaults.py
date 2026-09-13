"""Engine builtin plot drawings — packing catalog when world registry has no layout rows.

Each file in ``fixtures/templates/{stem}.json`` is a plot: ``occupied_footprint`` +
``main_building``. ``inn_small`` nests the tavern body; ``tavern_1`` / ``tavern_2`` /
``manor_1`` are the same plot shape for ``debug_structure``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate

_FIXTURES_TEMPLATES = (
    Path(__file__).resolve().parents[5] / "fixtures" / "templates"
)

_PACKING_STEMS: tuple[str, ...] = (
    "town_hall",
    "inn_small",
    "mine",
    "mill",
    "smelter",
    "workshop",
    "temple",
    "theater",
    "library",
    "farm",
    "livestock",
)


def _load_fixture_layout(stem: str) -> BuildingLayoutTemplate:
    path = _FIXTURES_TEMPLATES / f"{stem}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BuildingLayoutTemplate.model_validate(raw)


def canonical_defaults() -> list[BuildingLayoutTemplate]:
    """Builtin plot catalog merged under world layout-shaped rows."""
    return [_load_fixture_layout(stem) for stem in _PACKING_STEMS]
