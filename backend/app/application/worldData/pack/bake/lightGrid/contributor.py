"""LightGridContributor protocol — tz_map_light_bake."""

from __future__ import annotations

from typing import Protocol

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose


class LightGridContributor(Protocol):
    name: str

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None: ...
