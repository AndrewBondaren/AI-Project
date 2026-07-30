"""PeakAssembler — RidgeCandidate + policy → MountainSpec (tz_mountain_architecture)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.ridgePlacement import RidgeCandidate
from app.dataModel.terrainMasks.mountain.specs import MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy


def assemble_peak_from_policy(
    *,
    origin_x_m: int,
    origin_y_m: int,
    policy: MountainsCategoryPolicy,
    location_uid: str | None = None,
) -> MountainSpec:
    return MountainSpec(
        origin_x_m=origin_x_m,
        origin_y_m=origin_y_m,
        radius_m=int(policy.default_radius_m),
        kind=policy.default_kind,
        form=policy.default_form,
        sides=policy.resolved_sides(),
        location_uid=location_uid,
    )


def assemble_peaks_from_candidates(
    candidates: list[RidgeCandidate],
    policy: MountainsCategoryPolicy,
) -> list[MountainSpec]:
    return [
        assemble_peak_from_policy(
            origin_x_m=c.origin_x_m,
            origin_y_m=c.origin_y_m,
            policy=policy,
        )
        for c in candidates
    ]
