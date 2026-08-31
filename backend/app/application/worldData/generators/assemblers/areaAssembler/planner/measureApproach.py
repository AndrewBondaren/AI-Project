"""Peek abutting street z and measure approach ray — C21 / connections §5.1.1."""

from __future__ import annotations

from collections.abc import Mapping, Set

from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import (
    ApproachForm,
    StreetApproach,
)
from app.application.worldData.generators.coordinates.approachZ import classify_approach
from app.application.worldData.generators.coordinates.gridRay import walk_grid_ray
from app.dataModel.spatial.facing import GRID_OUTWARD_DELTA, Facing

Coord = tuple[int, int]

DEFAULT_APPROACH_MAX_K = 64


def peek_abutting_street_z(
    origin: Coord,
    facing: Facing,
    street_xy: Set[Coord],
    surface: Mapping[Coord, int],
) -> int | None:
    """One step along facing. Not a ray."""
    delta = GRID_OUTWARD_DELTA.get(facing)
    if delta is None:
        return None
    cell = (int(origin[0]) + delta[0], int(origin[1]) + delta[1])
    if cell not in street_xy:
        return None
    if cell in surface:
        return int(surface[cell])
    return 0


def measure_street_approach(
    origin: Coord,
    facing: Facing,
    z_near: int,
    street_xy: Set[Coord],
    surface: Mapping[Coord, int],
    *,
    max_k: int = DEFAULT_APPROACH_MAX_K,
) -> StreetApproach:
    z_far = peek_abutting_street_z(origin, facing, street_xy, surface)
    near = int(z_near)
    if z_far is None or near == z_far:
        return StreetApproach(
            ray=(),
            length=0,
            z_far=near if z_far is None else z_far,
            z_near=near,
            theta_rad=0.0,
            form=ApproachForm.NONE,
        )
    ray = walk_grid_ray(
        origin, facing, max_k=max_k, stop=lambda c, _k: c in street_xy,
    )
    if not ray:
        return StreetApproach(
            ray=(),
            length=0,
            z_far=z_far,
            z_near=near,
            theta_rad=0.0,
            form=ApproachForm.NONE,
        )
    end = ray[-1]
    z_end = int(surface[end]) if end in surface else z_far
    theta, form = classify_approach(abs(near - z_end), len(ray))
    return StreetApproach(
        ray=ray,
        length=len(ray),
        z_far=z_end,
        z_near=near,
        theta_rad=theta,
        form=form,
    )
