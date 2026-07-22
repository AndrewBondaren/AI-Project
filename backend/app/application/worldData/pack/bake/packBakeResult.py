"""Unified pack bake HTTP/application result — light / full / detailed (WP-27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.worldData.materializationContext import MaterializationJobReport
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
    PackDetailedBakeResult,
)
from app.application.worldData.persistResult import PersistResult
from app.dataModel.worldPack.packBakeMode import PackBakeApiMode


@dataclass
class PackBakeResult:
    """Single response shape for all pack bake modes."""

    mode: PackBakeApiMode
    terrain_failed: int = 0
    report: MaterializationJobReport | None = None
    detailed: PackDetailedBakeResult | PersistResult | None = None
    climate_fine_tiles: int | None = None
    loading_progress: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        if self.report is not None:
            payload = self.report.to_dict()
        elif isinstance(self.detailed, PackDetailedBakeResult):
            payload = {
                **self.detailed.terrain.to_dict(),
                "scope": self.detailed.scope,
                "tiles_refined": self.detailed.tiles_refined,
                "wilderness_chunks": self.detailed.wilderness_chunks,
                "climate_fine_tiles": self.detailed.climate_fine_tiles,
            }
            if self.detailed.location_uid is not None:
                payload["location_uid"] = self.detailed.location_uid
        elif self.detailed is not None:
            payload = self.detailed.to_dict()
        else:
            payload = {}
        if self.climate_fine_tiles is not None and "climate_fine_tiles" not in payload:
            payload["climate_fine_tiles"] = self.climate_fine_tiles
        return {
            **payload,
            "pack_mode": self.mode,
            "loading_progress": self.loading_progress,
        }
