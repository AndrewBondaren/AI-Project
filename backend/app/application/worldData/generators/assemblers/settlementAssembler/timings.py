"""Wall timings for one ``SettlementAssembler.assemble`` (seconds).

Orchestrator copies these onto ``SettlementPipelineTimings`` (C11 log / HTTP).
Generators do not call ``packBakeLog``.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class SettlementAssembleTimings:
    cache_s: float = 0.0
    packing_s: float = 0.0
    area_s: float = 0.0
    streets_s: float = 0.0
    barriers_s: float = 0.0
    occupancy_s: float = 0.0
    generate_s: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {item.name: round(float(getattr(self, item.name)), 3) for item in fields(self)}
