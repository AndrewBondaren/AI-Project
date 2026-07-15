"""Unified pack bake HTTP/application result — light / full / detailed (WP-27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.worldData.materializationContext import MaterializationJobReport
from app.application.worldData.persistResult import PersistResult
from app.dataModel.worldPack.packBakeMode import PackBakeApiMode


@dataclass
class PackBakeResult:
    """Single response shape for all pack bake modes."""

    mode: PackBakeApiMode
    terrain_failed: int = 0
    report: MaterializationJobReport | None = None
    detailed: PersistResult | None = None
    loading_progress: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        if self.report is not None:
            payload = self.report.to_dict()
        elif self.detailed is not None:
            payload = self.detailed.to_dict()
        else:
            payload = {}
        return {
            **payload,
            "pack_mode": self.mode,
            "loading_progress": self.loading_progress,
        }
