import logging

from dataclasses import dataclass

from app.application.jsonValidation import climate_scalars
from app.application.worldData.generators.assemblers.climateAssembler.types import ClimateRecalcRequest
from app.application.worldData.generators.climate.climateAnchor import AnchorSource
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.assemblers.climateAssembler.passes.anchorCollectPass import (
    run_anchor_collect_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.cellWeatherPass import (
    run_cell_weather_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.heightmapPass import (
    run_heightmap_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.liquidOverlayPass import (
    run_liquid_overlay_pass,
)
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClimateSurfaceResult:
    pole_field:      ClimatePoleField
    heightmap_cells: list[MapCell]
    anchor_field:    ClimateAnchorField
    surface_cells:   list[MapCell]


def _z_range(cells: list[MapCell]) -> tuple[int | None, int | None]:
    if not cells:
        return None, None
    zs = [c.z for c in cells]
    return min(zs), max(zs)


def _count_anchors(field: ClimateAnchorField) -> tuple[int, int, int]:
    manual = auto = admin = 0
    for anchor in field.anchors:
        if anchor.source == AnchorSource.MANUAL:
            manual += 1
        elif anchor.source == AnchorSource.AUTO:
            auto += 1
        elif anchor.source == AnchorSource.ADMIN:
            admin += 1
    return manual, auto, admin


class ClimateSurfaceAssembler:
    """
    Orchestrates surface climate passes. Entry at any pass level (for future DAG nodes).

    Non-surface anchors (map_z != 0) are not merged into eager map_cells (NC-1c);
    lazy repair — ``TerrainGeneratorService.generate_minimal``; volume climate TBD.
    """

    def __init__(self, climate: ClimateGeneratorService | None = None) -> None:
        self._climate = climate or ClimateGeneratorService()

    def assemble_full(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> ClimateSurfaceResult:
        scalars = climate_scalars(world)
        pole_field = run_pole_resolve_pass(world, locations)
        logger.info(
            "climate pass | world=%s pole_resolve | poles=%d preset=%s mode=%s",
            world.world_uid,
            len(pole_field.poles),
            scalars.climate_pole_preset,
            scalars.climate_pole_mode,
        )

        heightmap = run_heightmap_pass(world, locations, pole_field)
        z_lo, z_hi = _z_range(heightmap)
        logger.info(
            "climate pass | world=%s heightmap | cells=%d z_range=[%s,%s]",
            world.world_uid,
            len(heightmap),
            z_lo,
            z_hi,
        )

        anchor_field = run_anchor_collect_pass(
            world, locations, heightmap, pole_field,
        )
        manual_n, auto_n, admin_n = _count_anchors(anchor_field)
        logger.info(
            "climate pass | world=%s anchor_collect | manual=%d auto=%d admin=%d total=%d admin_skipped=%s",
            world.world_uid,
            manual_n,
            auto_n,
            admin_n,
            len(anchor_field.anchors),
            not pole_field.is_empty(),
        )

        surface = run_cell_weather_pass(
            world, locations, pole_field, anchor_field, heightmap, self._climate,
        )
        logger.info(
            "climate pass | world=%s cell_weather | surface_cells=%d path=resolve_climate",
            world.world_uid,
            len(surface),
        )

        return ClimateSurfaceResult(
            pole_field=pole_field,
            heightmap_cells=heightmap,
            anchor_field=anchor_field,
            surface_cells=surface,
        )

    def apply_climate_pass(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
    ) -> list[MapCell]:
        """Climate pass on existing terrain cells: weather + liquid overlay."""
        pole_field = run_pole_resolve_pass(world, locations)
        anchor_field = run_anchor_collect_pass(
            world, locations, heightmap_cells, pole_field,
        )
        weathered = run_cell_weather_pass(
            world, locations, pole_field, anchor_field, heightmap_cells, self._climate,
        )
        overlaid = run_liquid_overlay_pass(world, weathered)
        logger.info(
            "climate pass | world=%s apply_climate | cells=%d liquid_overlay=%d",
            world.world_uid,
            len(weathered),
            len(overlaid),
        )
        return overlaid

    def heightmap_only(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> list[MapCell]:
        pole_field = run_pole_resolve_pass(world, locations)
        return run_heightmap_pass(world, locations, pole_field)

    def apply_weather_only(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
        pole_field: ClimatePoleField | None = None,
        anchor_field: ClimateAnchorField | None = None,
    ) -> list[MapCell]:
        poles = pole_field or run_pole_resolve_pass(world, locations)
        field = anchor_field or run_anchor_collect_pass(
            world, locations, heightmap_cells, poles,
        )
        return run_cell_weather_pass(
            world, locations, poles, field, heightmap_cells, self._climate,
        )

    def recalculate(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
        request: ClimateRecalcRequest,
    ) -> list[MapCell]:
        """
        Partial climate update — separate process from assemble_full (see tz_climate.md).
        Executes passes per ClimateRecalcRequest; returns subset of cells for upsert.
        """
        result = self.apply_weather_only(world, locations, heightmap_cells)
        if request.run_cell_weather:
            result = run_liquid_overlay_pass(world, result)
        return result
