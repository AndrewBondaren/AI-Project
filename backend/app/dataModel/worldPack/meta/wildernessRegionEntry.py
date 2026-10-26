"""Bake-time coverage index. No resolved Specs or live state in this wire."""
from __future__ import annotations
from collections.abc import Sequence
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, model_validator
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


class WildernessRegionStatus(StrEnum):
    DECLARED = "declared"
    ANCHOR = "anchor"
    AUTORESOLVED = "autoresolved"
    SUBLOCATION = "sublocation"


class RegionIndexBounds(BaseModel):
    """Inclusive conservative AABB in canonical world fine-cell coordinates."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @model_validator(mode="after")
    def ordered(self) -> RegionIndexBounds:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("region bbox requires ordered bounds")
        return self


class WildernessRegionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    region_uid: str
    entry_type: TerrainKey
    current_type: TerrainKey
    bbox: RegionIndexBounds
    status: WildernessRegionStatus
    parent_region_uid: str | None = None
    spec_fingerprint: str | None = None

    @model_validator(mode="after")
    def parent_contract(self) -> WildernessRegionEntry:
        if self.status is WildernessRegionStatus.SUBLOCATION:
            if not self.parent_region_uid or self.parent_region_uid == self.region_uid:
                raise ValueError("sublocation requires a distinct parent UID")
        elif self.parent_region_uid is not None:
            raise ValueError("only sublocations have parent_region_uid")
        return self


def require_region_index(entries: Sequence[WildernessRegionEntry]) -> None:
    by_uid: dict[str, WildernessRegionEntry] = {}
    for entry in entries:
        if entry.region_uid in by_uid:
            raise ValueError(f"duplicate wilderness entity UID: {entry.region_uid}")
        by_uid[entry.region_uid] = entry
    for entry in entries:
        if entry.parent_region_uid is not None:
            parent = by_uid.get(entry.parent_region_uid)
            if parent is None or parent.status is WildernessRegionStatus.SUBLOCATION:
                raise ValueError(f"missing or invalid parent for {entry.region_uid}")
