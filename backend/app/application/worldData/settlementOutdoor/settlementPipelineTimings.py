"""Wall timings for outdoor C11 packing and C23 topology.

Serial stages: named parts sum to ≤ ``c11_s`` / ``topology_s``. Remainder is
skip-checks and cheap glue. Do **not** name generate time ``materialize_s``
(that key is FineTerrain column fill in ``GradePipelineTimings``).

SoT keys: ``docs/tz_application_performance.md``, ``docs/tz_settlement_outdoor.md``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, fields, replace
from typing import Any

from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)


def _r(value: float) -> float:
    return round(float(value), 3)


class WallClock:
    """Lap timer: ``lap()`` is seconds since the previous lap or start."""

    __slots__ = ("_origin", "_mark")

    def __init__(self) -> None:
        now = time.perf_counter()
        self._origin = now
        self._mark = now

    def lap(self) -> float:
        now = time.perf_counter()
        dt = now - self._mark
        self._mark = now
        return dt

    def total(self) -> float:
        return time.perf_counter() - self._origin


_C11_SUFFIX_KEYS = (
    "setup_s",
    "terrain_s",
    "catalog_s",
    "topology_s",
    "generate_s",
    "assemble_cache_s",
    "assemble_packing_s",
    "assemble_area_s",
    "assemble_streets_s",
    "assemble_barriers_s",
    "assemble_occupancy_s",
    "extract_s",
    "encode_s",
    "sql_s",
    "publish_s",
    "c11_s",
)

_TOPOLOGY_SUFFIX_KEYS = (
    "setup_s",
    "topo_terrain_s",
    "topo_slots_s",
    "topo_streets_s",
    "topo_extract_s",
    "topo_sql_s",
    "topology_s",
)


@dataclass(frozen=True, slots=True)
class SettlementPipelineTimings:
    setup_s: float = 0.0
    terrain_s: float = 0.0
    catalog_s: float = 0.0
    topology_s: float = 0.0
    generate_s: float = 0.0
    assemble_cache_s: float = 0.0
    assemble_packing_s: float = 0.0
    assemble_area_s: float = 0.0
    assemble_streets_s: float = 0.0
    assemble_barriers_s: float = 0.0
    assemble_occupancy_s: float = 0.0
    extract_s: float = 0.0
    encode_s: float = 0.0
    sql_s: float = 0.0
    publish_s: float = 0.0
    c11_s: float = 0.0
    topo_terrain_s: float = 0.0
    topo_slots_s: float = 0.0
    topo_streets_s: float = 0.0
    topo_extract_s: float = 0.0
    topo_sql_s: float = 0.0

    @classmethod
    def from_parts(
        cls,
        *,
        assemble: SettlementAssembleTimings | None = None,
        topology: SettlementPipelineTimings | None = None,
        **values: float,
    ) -> SettlementPipelineTimings:
        payload: dict[str, float] = dict(values)
        if assemble is not None:
            payload.setdefault("assemble_cache_s", assemble.cache_s)
            payload.setdefault("assemble_packing_s", assemble.packing_s)
            payload.setdefault("assemble_area_s", assemble.area_s)
            payload.setdefault("assemble_streets_s", assemble.streets_s)
            payload.setdefault("assemble_barriers_s", assemble.barriers_s)
            payload.setdefault("assemble_occupancy_s", assemble.occupancy_s)
        if topology is not None:
            payload.setdefault("topo_terrain_s", topology.topo_terrain_s)
            payload.setdefault("topo_slots_s", topology.topo_slots_s)
            payload.setdefault("topo_streets_s", topology.topo_streets_s)
            payload.setdefault("topo_extract_s", topology.topo_extract_s)
            payload.setdefault("topo_sql_s", topology.topo_sql_s)
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in payload.items() if key in known})

    def with_c11_wall(self, c11_s: float) -> SettlementPipelineTimings:
        return replace(self, c11_s=c11_s)

    def as_dict(self) -> dict[str, float]:
        return {item.name: _r(getattr(self, item.name)) for item in fields(self)}

    @classmethod
    def wire_keys(cls) -> tuple[str, ...]:
        return tuple(item.name for item in fields(cls))

    def _suffix(self, keys: tuple[str, ...]) -> str:
        d = self.as_dict()
        return "".join(f" {key}={d[key]:.2f}" for key in keys)

    def c11_log_suffix(self) -> str:
        return self._suffix(_C11_SUFFIX_KEYS)

    def topology_log_suffix(self) -> str:
        return self._suffix(_TOPOLOGY_SUFFIX_KEYS)

    def c11_log_fields(self) -> dict[str, Any]:
        d = self.as_dict()
        return {key: d[key] for key in _C11_SUFFIX_KEYS}

    def topology_log_fields(self) -> dict[str, Any]:
        d = self.as_dict()
        return {key: d[key] for key in _TOPOLOGY_SUFFIX_KEYS}
