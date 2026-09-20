"""Attach C11/C23 pipeline onto results and write packBakeLog."""

from __future__ import annotations

from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_c11_done,
    log_pack_settlement_topology_done,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeResult,
    TopologyResult,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)


def finish_c11(
    world_uid: str,
    result: MaterializeResult,
    clock: WallClock,
    *,
    pipeline: SettlementPipelineTimings | None = None,
    encode_bytes: int | None = None,
) -> MaterializeResult:
    timings = (pipeline or SettlementPipelineTimings()).with_c11_wall(clock.total())
    result.pipeline_s = timings
    log_pack_settlement_c11_done(
        world_uid,
        location_uid=result.location_uid,
        status=result.status,
        pipeline=timings,
        districts=result.districts,
        buildings=result.buildings,
        entry_points=result.entry_points,
        encode_bytes=encode_bytes,
    )
    return result


def skipped_c11(
    world_uid: str, location_uid: str, clock: WallClock,
) -> MaterializeResult:
    return finish_c11(
        world_uid,
        MaterializeResult(location_uid=location_uid, status="skipped"),
        clock,
        pipeline=SettlementPipelineTimings(setup_s=clock.total()),
    )


def finish_c11_error(world_uid: str, location_uid: str, clock: WallClock) -> None:
    log_pack_settlement_c11_done(
        world_uid,
        location_uid=location_uid,
        status="error",
        pipeline=SettlementPipelineTimings(c11_s=clock.total()),
    )


def finish_topology(
    world_uid: str,
    result: TopologyResult,
    clock: WallClock,
    *,
    pipeline: SettlementPipelineTimings | None = None,
) -> TopologyResult:
    timings = pipeline or SettlementPipelineTimings(topology_s=clock.total())
    result.pipeline_s = timings
    log_pack_settlement_topology_done(
        world_uid,
        location_uid=result.location_uid,
        status=result.status,
        pipeline=timings,
        districts=result.districts,
        gates=result.gates,
    )
    return result


def finish_topology_error(
    world_uid: str, location_uid: str, clock: WallClock,
) -> None:
    log_pack_settlement_topology_done(
        world_uid,
        location_uid=location_uid,
        status="error",
        pipeline=SettlementPipelineTimings(topology_s=clock.total()),
    )
