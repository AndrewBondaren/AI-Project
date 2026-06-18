"""
External vertical ladder — лестница снаружи здания.
Наследует VerticalLadderBuilder, всегда on_the_edge=True, near_wall=True.
ТЗ: docs/tz_staircase_generation.md §8
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

    def build(self):
        entry = dict(self.sc_entry or {})
        entry["on_the_edge"] = True
        entry["near_wall"]   = True
        self.sc_entry = entry
        return super().build()
