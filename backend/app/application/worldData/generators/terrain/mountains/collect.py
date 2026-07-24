"""Collect mountain Specs — declare / anchors / autoresolve (tz_map_light_bake)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.terrain.mountains.geoAnchors import (
    anchor_mountain_locations,
)
from app.application.worldData.generators.terrain.mountains.ridgePlacement import (
    iter_ridge_cells_in_meter_rect,
    place_ridge_candidates,
)
from app.application.worldData.masks.mergeDeclare import merge_declare_over_auto
from app.application.worldData.pack.bake.lightGrid.coords import (
    light_to_macro_local,
    meters_to_light,
)
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import (
    MountainsCategoryPolicy,
    WorldTerrainMasks,
)

if TYPE_CHECKING:
    from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.world import World


def _spec_from_policy(
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


def load_declared_mountains(masks: WorldTerrainMasks) -> list[MountainSpec | MountainRangeSpec]:
    return list(masks.declared_mountains)


def specs_from_geographic_locations(
    locations: list[NamedLocation],
    policy: MountainsCategoryPolicy,
) -> list[MountainSpec]:
    """Anchor Specs from geographic.mountain/peak — not declare-path / not wire declared_*."""
    out: list[MountainSpec] = []
    for loc in anchor_mountain_locations(locations):
        out.append(
            _spec_from_policy(
                origin_x_m=int(loc.map_x),
                origin_y_m=int(loc.map_y),
                policy=policy,
                location_uid=loc.location_uid,
            )
        )
    return out


def merge_mountain_spec_sources(
    *,
    declared: list[MountainSpec | MountainRangeSpec],
    anchors: list[MountainSpec],
    auto: list[MountainSpec],
) -> list[MountainSpec | MountainRangeSpec]:
    """Shared merge SoT: declared > anchors > autoresolve (identity_key). Q15/Q17."""
    key = lambda s: s.identity_key()
    base = merge_declare_over_auto(declared, anchors, key=key)
    return merge_declare_over_auto(base, auto, key=key)


def _typical_from_pole(pole_field, world, gx: int, gy: int) -> int:
    """Q9: typed ``ClimatePoleSample.typical_elevation_z`` (no getattr)."""
    if pole_field is None:
        return 0
    sample = pole_field.sample(world, gx, gy)
    return int(sample.typical_elevation_z)


def autoresolve_mountain_specs(
    ctx: LightGridBakeContext,
    policy: MountainsCategoryPolicy,
) -> list[MountainSpec]:
    """Placement A: ridge-quantized candidates → MountainSpec (not score→paint)."""
    if not policy.autoresolve:
        return []
    seed = world_seed(ctx.world)
    scale = ctx.scale
    tile_set = set(ctx.tiles)
    cells: list[tuple[int, int, int, int]] = []
    for gx, gy in ctx.tiles:
        x0 = gx * scale.tile_m
        y0 = gy * scale.tile_m
        x1 = x0 + scale.tile_m - 1
        y1 = y0 + scale.tile_m - 1
        cells.extend(
            iter_ridge_cells_in_meter_rect(
                x0=x0, y0=y0, x1=x1, y1=y1, ridge_cell_m=int(policy.ridge_cell_m),
            )
        )

    def _typical(ox: int, oy: int) -> int:
        lx, ly = meters_to_light(ox, oy, scale)
        mgx, mgy, _tx, _ty = light_to_macro_local(lx, ly, scale)
        return _typical_from_pole(ctx.pole_field, ctx.world, mgx, mgy)

    def _accept(ox: int, oy: int) -> bool:
        lx, ly = meters_to_light(ox, oy, scale)
        mgx, mgy, _tx, _ty = light_to_macro_local(lx, ly, scale)
        return (mgx, mgy) in tile_set

    candidates = place_ridge_candidates(
        seed=seed,
        policy=policy,
        cells=cells,
        typical_of=_typical,
        accept=_accept,
    )
    return [
        _spec_from_policy(origin_x_m=c.origin_x_m, origin_y_m=c.origin_y_m, policy=policy)
        for c in candidates
    ]


def collect_mountain_entries_for_coarse(
    world: World,
    locations: list[NamedLocation],
    masks: WorldTerrainMasks,
    *,
    policy: MountainsCategoryPolicy,
    pole_field,
    heightmap_keys: set[tuple[int, int]],
    cell_m: int,
) -> list[MountainSpec | MountainRangeSpec]:
    """Pass 1.4 collect — same merge SoT as light (Q3-A: no Range→disk expand)."""
    declared = load_declared_mountains(masks)
    anchors = specs_from_geographic_locations(locations, policy)
    auto: list[MountainSpec] = []
    if policy.autoresolve:
        seed = world_seed(world)
        cells: list[tuple[int, int, int, int]] = []
        ridge_m = max(1, int(policy.ridge_cell_m))
        seen_q: set[tuple[int, int]] = set()
        for gx, gy in heightmap_keys:
            xm = gx * cell_m + cell_m // 2
            ym = gy * cell_m + cell_m // 2
            qx, qy = xm // ridge_m, ym // ridge_m
            if (qx, qy) in seen_q:
                continue
            seen_q.add((qx, qy))
            cells.append((qx, qy, qx * ridge_m + ridge_m // 2, qy * ridge_m + ridge_m // 2))

        def _typical(ox: int, oy: int) -> int:
            gx = ox // max(1, cell_m)
            gy = oy // max(1, cell_m)
            return _typical_from_pole(pole_field, world, gx, gy)

        candidates = place_ridge_candidates(
            seed=seed,
            policy=policy,
            cells=cells,
            typical_of=_typical,
        )
        auto = [
            _spec_from_policy(origin_x_m=c.origin_x_m, origin_y_m=c.origin_y_m, policy=policy)
            for c in candidates
        ]
    return merge_mountain_spec_sources(
        declared=declared, anchors=anchors, auto=auto,
    )


# Back-compat alias
collect_mountain_specs_for_coarse = collect_mountain_entries_for_coarse
