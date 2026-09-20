"""Outdoor settlement HTTP/application contract — errors and result DTOs.

Registry helpers stay in ``settlementOutdoorTypes.py``. Callers import from here,
not from the orchestrator module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
)


class SettlementOutdoorError(Exception):
    """Outdoor materialize domain error."""


class SettlementOutdoorNotFoundError(SettlementOutdoorError):
    pass


class SettlementOutdoorPackMissingError(SettlementOutdoorError):
    pass


class SettlementOutdoorConflictError(SettlementOutdoorError):
    pass


@dataclass
class MaterializeResult:
    location_uid: str
    status: str
    districts: int = 0
    buildings: int = 0
    levels: int = 0
    entry_points: int = 0
    dominant_material: str | None = None
    error: str | None = None
    pipeline_s: SettlementPipelineTimings | None = None

    def to_dict(self) -> dict:
        payload = {
            "location_uid": self.location_uid,
            "status": self.status,
            "districts": self.districts,
            "buildings": self.buildings,
            "levels": self.levels,
            "entry_points": self.entry_points,
            "dominant_material": self.dominant_material,
        }
        if self.error:
            payload["error"] = self.error
        if self.pipeline_s is not None:
            payload["c11_pipeline"] = self.pipeline_s.as_dict()
        return payload


@dataclass
class MaterializeBatchResult:
    results: list[MaterializeResult] = field(default_factory=list)
    failed_uids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "failed_uids": self.failed_uids,
        }


@dataclass
class TopologyResult:
    location_uid: str
    status: str
    districts: int = 0
    gates: int = 0
    error: str | None = None
    pipeline_s: SettlementPipelineTimings | None = None

    def to_dict(self) -> dict:
        payload = {
            "location_uid": self.location_uid,
            "status": self.status,
            "districts": self.districts,
            "gates": self.gates,
        }
        if self.error:
            payload["error"] = self.error
        if self.pipeline_s is not None:
            payload["topology_pipeline"] = self.pipeline_s.as_dict()
        return payload


@dataclass
class TopologyBatchResult:
    results: list[TopologyResult] = field(default_factory=list)
    failed_uids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "failed_uids": self.failed_uids,
        }
