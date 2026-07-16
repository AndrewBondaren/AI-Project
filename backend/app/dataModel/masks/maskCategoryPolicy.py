"""Shared enabled/autoresolve for mask-domain category policies.

Used by hydrology categories and ``world.terrain_masks`` — tz_map_light_bake § Surface mask domains.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire


class MaskCategoryPolicy(BaseModel):
    """Common gate: enabled default true; autoresolve default true."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultOnWire[bool] = True
    autoresolve: DefaultOnWire[bool] = True
