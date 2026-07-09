"""Climate batch materialization — parallel compute, serial persist.

Symmetry with ``TerrainBatchOrchestrator``. Pure passes stay in
``ClimateSurfaceAssembler``; this module owns pool + ``save_pass`` queue.

See ``docs/tz_climate.md`` § CL-PAR (impl).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.api.schemas.imports import ImportResult
from app.application.worldData.chunkComputePool import ChunkComputePool, split_contiguous_batches
from app.application.worldData.generators.assemblers.climateAssembler.passes.anchorCollectPass import (
    run_anchor_collect_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.cellWeatherPass import (
    run_cell_weather_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.liquidOverlayPass import (
    build_surface_top_index,
    run_liquid_overlay_batch,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.parallelPolicy import resolve_climate_workers
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

if TYPE_CHECKING:
    from app.application.worldData.bootstrapMapCellWriter import BootstrapMapCellWriter

logger = logging.getLogger(__name__)


class ClimateBatchOrchestrator:
    """Pole/anchor serial → parallel weather/overlay → serial climate persist."""

    def __init__(
        self,
        map_cell_service: MapCellService,
        climate: ClimateGeneratorService | None = None,
    ) -> None:
        self._map_cells = map_cell_service
        self._climate = climate or ClimateGeneratorService()

    async def apply_climate_batch(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        cells: list[MapCell] | None = None,
        *,
        bootstrap_writer: BootstrapMapCellWriter | None = None,
    ) -> tuple[ImportResult, int, int]:
        """
        Climate on existing terrain cells.

        Returns ``(import_result, batches_done, batches_total)``.
        """
        heightmap_cells = cells if cells is not None else await self._map_cells.get_all(world_uid)
        if not heightmap_cells:
            return ImportResult(total=0, succeeded=0, failed=0), 0, 0

        workers = resolve_climate_workers(ctx, world)
        pole_field = run_pole_resolve_pass(world, locations)
        anchor_field = run_anchor_collect_pass(
            world, locations, heightmap_cells, pole_field,
        )

        batches = split_contiguous_batches(heightmap_cells, workers)
        batches_total = len(batches)

        def weather_batch(batch: list[MapCell]) -> list[MapCell]:
            return run_cell_weather_pass(
                world, locations, pole_field, anchor_field, batch, self._climate,
            )

        pool = ChunkComputePool(workers)
        if batches_total <= 1:
            weathered_parts = [weather_batch(heightmap_cells)]
        else:
            weathered_parts = await pool.map_sync(batches, weather_batch)

        weathered: list[MapCell] = []
        for part in weathered_parts:
            weathered.extend(part)

        surface_top = build_surface_top_index(weathered)
        overlay_batches = split_contiguous_batches(weathered, workers)

        def overlay_batch(batch: list[MapCell]) -> list[MapCell]:
            return run_liquid_overlay_batch(world, batch, surface_top)

        if len(overlay_batches) <= 1:
            overlaid = overlay_batch(weathered)
        else:
            overlaid_parts = await pool.map_sync(overlay_batches, overlay_batch)
            overlaid = []
            for part in overlaid_parts:
                overlaid.extend(part)

        if bootstrap_writer is not None:
            n = await bootstrap_writer.write_climate(overlaid)
            result = ImportResult(total=len(overlaid), succeeded=n, failed=0)
        else:
            result = await self._map_cells.save_pass(overlaid, "climate")
        logger.info(
            "apply_climate_batch | world=%s cells=%d workers=%d batches=%d upserted=%d",
            world_uid, len(overlaid), workers, batches_total, result.succeeded,
        )
        return result, batches_total, batches_total
