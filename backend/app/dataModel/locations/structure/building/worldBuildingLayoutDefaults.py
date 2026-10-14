"""Engine builtin plot drawings — packing catalog when world registry has no layout rows.

Every ``fixtures/templates/*.json`` is a ``PlotLayoutTemplate``:
``occupied_footprint`` + ``main_building.structure`` uid ref into
``structures_templates/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate

_FIXTURES_TEMPLATES = (
    Path(__file__).resolve().parents[6] / "fixtures" / "templates"
)

# Trusted shipped source identities; adding an arbitrary file never declares a default.
CANONICAL_PLOT_NAMES = (
    "farm", "inn_small", "library", "livestock", "mill", "mine", "smelter",
    "temple", "theater", "town_hall", "workshop",
)


def _load_fixture_layout(path: Path) -> PlotLayoutTemplate:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PlotLayoutTemplate.model_validate(raw)


def canonical_defaults(*, source_root: Path | None = None) -> list[PlotLayoutTemplate]:
    """Builtin plot catalog merged under world layout-shaped rows.

    ``plot_type``-defaulted plots are returned as-is; the caller (application
    layer) reports them via ``plot_type_defaulted`` + ``packing_warning``.
    """
    plots: list[PlotLayoutTemplate] = []
    for name in CANONICAL_PLOT_NAMES:
        plots.append(_load_fixture_layout((source_root or _FIXTURES_TEMPLATES) / f"{name}.json"))
    return plots
