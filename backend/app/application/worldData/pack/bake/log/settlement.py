"""Settlement pack diagnostics — C11 packing + topology batches."""

from __future__ import annotations

import time

from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
)

from ._shared import _error, _info


def log_pack_settlement_skip_not_in_index(
    world_uid: str,
    *,
    location_uid: str,
) -> None:
    _error(
        "pack settlement error | world=%s location=%s "
        "not a locations_index pin (occupancy); packing skipped "
        "reason=not_in_locations_index",
        world_uid,
        location_uid,
        activity="settlement_c11_skip",
        world_uid=world_uid,
        location_uid=location_uid,
        reason="not_in_locations_index",
    )


def log_pack_settlement_c11_start(world_uid: str, *, location_uid: str) -> None:
    _info(
        "pack settlement c11 start | world=%s location=%s",
        world_uid,
        location_uid,
        activity="settlement_c11_start",
        world_uid=world_uid,
        location_uid=location_uid,
    )


def log_pack_settlement_c11_done(
    world_uid: str,
    *,
    location_uid: str,
    status: str,
    pipeline: SettlementPipelineTimings | None = None,
    districts: int = 0,
    buildings: int = 0,
    entry_points: int = 0,
    encode_bytes: int | None = None,
) -> None:
    """Wall C11 after L2. ``materialize_s`` is FineTerrain fill — not this line."""
    timings = pipeline or SettlementPipelineTimings()
    bytes_part = f" encode_bytes={encode_bytes}" if encode_bytes is not None else ""
    _info(
        "pack settlement c11 done | world=%s location=%s status=%s "
        "districts=%d buildings=%d entries=%d%s%s",
        world_uid,
        location_uid,
        status,
        districts,
        buildings,
        entry_points,
        bytes_part,
        timings.c11_log_suffix(),
        activity="settlement_c11_done",
        world_uid=world_uid,
        location_uid=location_uid,
        status=status,
        districts=districts,
        buildings=buildings,
        entry_points=entry_points,
        encode_bytes=encode_bytes,
        **timings.c11_log_fields(),
    )


def log_pack_settlement_topology_batch_start(world_uid: str, *, settlements: int) -> float:
    _info(
        "pack settlement topology batch start | world=%s settlements=%d",
        world_uid,
        settlements,
        activity="settlement_topology_batch_start",
        world_uid=world_uid,
        settlements=settlements,
    )
    return time.perf_counter()


def log_pack_settlement_topology_batch_done(
    world_uid: str,
    *,
    settlements: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack settlement topology batch done | world=%s settlements=%d elapsed_s=%.2f",
        world_uid,
        settlements,
        elapsed_s,
        activity="settlement_topology_batch_done",
        world_uid=world_uid,
        settlements=settlements,
        elapsed_s=round(elapsed_s, 2),
    )


def log_pack_settlement_topology_start(world_uid: str, *, location_uid: str) -> None:
    _info(
        "pack settlement topology start | world=%s location=%s",
        world_uid,
        location_uid,
        activity="settlement_topology_start",
        world_uid=world_uid,
        location_uid=location_uid,
    )


def log_pack_settlement_topology_done(
    world_uid: str,
    *,
    location_uid: str,
    status: str,
    pipeline: SettlementPipelineTimings | None = None,
    districts: int = 0,
    gates: int = 0,
) -> None:
    timings = pipeline or SettlementPipelineTimings()
    _info(
        "pack settlement topology done | world=%s location=%s status=%s "
        "districts=%d gates=%d%s",
        world_uid,
        location_uid,
        status,
        districts,
        gates,
        timings.topology_log_suffix(),
        activity="settlement_topology_done",
        world_uid=world_uid,
        location_uid=location_uid,
        status=status,
        districts=districts,
        gates=gates,
        **timings.topology_log_fields(),
    )
