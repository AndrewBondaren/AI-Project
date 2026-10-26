"""Compute-pool diagnostics for pack bake."""

from ._shared import _info


def log_pack_compute_pool(*, workers: int, max_in_flight: int) -> None:
    _info(
        "pack compute pool | workers=%d max_in_flight=%d",
        workers,
        max_in_flight,
        activity="compute_pool_create",
        pool_workers=workers,
        max_in_flight=max_in_flight,
    )
