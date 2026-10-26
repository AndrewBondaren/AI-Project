"""L0 settlement footprint on light grid — tz_map_light_bake settlement contributor."""

from __future__ import annotations

import math
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class LightSettlementFootprintPolicy(BaseModel):
    """Maps city_size map_cells_count → light-cell disk radius."""

    SCHEMA_ID: ClassVar[str] = "SCH-LIGHT-SETTLEMENT-FOOTPRINT"

    model_config = ConfigDict(extra="ignore", frozen=True)

    min_radius_light: int = Field(default=1, ge=1)
    # radius = max(min_radius, ceil(sqrt(count) * side / scale_divisor))
    scale_divisor: float = Field(default=8.0, gt=0.0)

    @classmethod
    def canonical_defaults(cls) -> LightSettlementFootprintPolicy:
        return cls()

    def radius_light(self, map_cells_count: int | None, side: int) -> int:
        count = max(1, int(map_cells_count) if map_cells_count is not None else 1)
        side_n = max(1, int(side))
        raw = math.ceil(math.sqrt(count) * (side_n / self.scale_divisor))
        return max(self.min_radius_light, int(raw))
