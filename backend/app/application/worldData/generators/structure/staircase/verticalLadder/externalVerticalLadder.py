"""
External vertical ladder — лестница снаружи здания.
Наследует VerticalLadderBuilder, всегда on_the_edge=True.
ТЗ: docs/tz_staircase_generation.md §8.1
"""
from __future__ import annotations

from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadder import (
    VerticalLadderBuilder,
)
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderValidator import (
    ExternalVerticalLadderValidator,
)


class ExternalVerticalLadderBuilder(VerticalLadderBuilder):
    _validator = ExternalVerticalLadderValidator()

    @property
    def _on_the_edge(self) -> bool:
        return True
