"""Pack L0 tile plan — single SoT for light/full expected tile sets (WP-27)."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

PackTilePlanScope = Literal["light", "full"]


class PackTileRef(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    gx: int
    gy: int

    def as_tuple(self) -> tuple[int, int]:
        return self.gx, self.gy


class PackTilePlan(BaseModel):
    """Output of ``PackTilePlanner`` — expected L0 macro-tiles for a bake scope."""

    SCHEMA_ID: ClassVar[str] = "SCH-PACK-TILE-PLAN"

    model_config = ConfigDict(extra="ignore", frozen=True)

    scope: PackTilePlanScope
    tiles: list[PackTileRef] = Field(default_factory=list)
    capped: bool = False
    cap_applied: int | None = None

    def tile_tuples(self) -> list[tuple[int, int]]:
        return [t.as_tuple() for t in self.tiles]
