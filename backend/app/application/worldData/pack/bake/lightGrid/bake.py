"""Run fixed contributor pipeline → LightGridCompose (tz_map_light_bake)."""

from __future__ import annotations

import logging
import time
from collections import Counter

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributor import LightGridContributor
from app.application.worldData.pack.bake.lightGrid.contributors.climate import ClimateContributor
from app.application.worldData.pack.bake.lightGrid.contributors.hydro import HydroContributor
from app.application.worldData.pack.bake.lightGrid.contributors.landcover import LandcoverContributor
from app.application.worldData.pack.bake.lightGrid.contributors.relief import ReliefContributor
from app.application.worldData.pack.bake.lightGrid.contributors.settlement import (
    SettlementContributor,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

logger = logging.getLogger(__name__)

DEFAULT_CONTRIBUTORS: tuple[LightGridContributor, ...] = (
    ReliefContributor(),
    LandcoverContributor(),
    HydroContributor(),
    SettlementContributor(),
    ClimateContributor(),
)


def compose_light_grid(
    ctx: LightGridBakeContext,
    *,
    contributors: tuple[LightGridContributor, ...] | None = None,
) -> LightGridCompose:
    compose = LightGridCompose(ctx.scale)
    pipeline = contributors or DEFAULT_CONTRIBUTORS
    t0 = time.perf_counter()
    logger.info(
        "light_compose_start | world=%s tiles=%d side=%d light_m=%d",
        ctx.world.world_uid,
        len(ctx.tiles),
        ctx.scale.side,
        ctx.scale.light_m,
    )
    for contributor in pipeline:
        c0 = time.perf_counter()
        contributor.apply(compose, ctx)
        logger.info(
            "light_compose_contributor | world=%s name=%s elapsed_ms=%.1f",
            ctx.world.world_uid,
            contributor.name,
            (time.perf_counter() - c0) * 1000.0,
        )
    hydro_hist: Counter[str] = Counter()
    pin_n = 0
    for gx, gy in ctx.tiles:
        for _tx, _ty, cell in compose.iter_tile(gx, gy):
            hydro_hist[cell.hydrology_role.name] += 1
            if cell.location_pin is not None:
                pin_n += 1
    non_none_hydro = sum(
        v for k, v in hydro_hist.items() if k != WorldMapHydrologyRole.NONE.name
    )
    logger.info(
        "light_compose_done | world=%s elapsed_ms=%.1f hydro_non_none=%d pins=%d hydro_hist=%s",
        ctx.world.world_uid,
        (time.perf_counter() - t0) * 1000.0,
        non_none_hydro,
        pin_n,
        dict(hydro_hist),
    )
    if non_none_hydro == 0 and pin_n == 0:
        logger.warning(
            "world_map_bake_all_flat | world=%s — compose left no hydro/pins on light mask",
            ctx.world.world_uid,
        )
    return compose
