"""Engine builtin plot drawings — packing catalog when world registry has no layout rows.

Every ``fixtures/templates/*.json`` is a ``PlotLayoutTemplate``:
``occupied_footprint`` + ``main_building.structure`` uid ref into
``structures_templates/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dataModel.structure.building.plotLayoutTemplate import PlotLayoutTemplate

_FIXTURES_TEMPLATES = (
    Path(__file__).resolve().parents[5] / "fixtures" / "templates"
)


def _load_fixture_layout(path: Path) -> PlotLayoutTemplate:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PlotLayoutTemplate.model_validate(raw)


def canonical_defaults() -> list[PlotLayoutTemplate]:
    """Builtin plot catalog merged under world layout-shaped rows.

    ``plot_type``-defaulted plots are returned as-is; the caller (application
    layer) reports them via ``plot_type_defaulted`` + ``packing_warning``.
    """
    plots: list[PlotLayoutTemplate] = []
    for path in sorted(_FIXTURES_TEMPLATES.glob("*.json")):
        plots.append(_load_fixture_layout(path))
    return plots
