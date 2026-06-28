import logging

from dataclasses import dataclass

from app.application.worldData.generators.assemblers.climateAssembler.types import RecalcTrigger
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
    """

    def __init__(self, climate: ClimateGeneratorService | None = None) -> None:
        self._climate = climate or ClimateGeneratorService()

    def assemble_full(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
    ) -> ClimateSurfaceResult:
        pole_field = run_pole_resolve_pass(world, locations, padding)
        logger.info(
            "climate pass | world=%s pole_resolve | poles=%d preset=%s mode=%s",
            world.world_uid,
            len(pole_field.poles),
            world.climate_pole_preset or "binary",
            world.climate_pole_mode or "autoresolve",
        )

        heightmap = run_heightmap_pass(world, locations, pole_field, padding)
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
        extra   = self._non_surface_anchor_cells(world, locations)
        logger.info(
            "climate pass | world=%s cell_weather | surface_cells=%d extra_non_surface=%d path=resolve_climate",
            world.world_uid,
            len(surface),
            len(extra),
        )

        return ClimateSurfaceResult(
            pole_field=pole_field,
            heightmap_cells=heightmap,
            anchor_field=anchor_field,
            surface_cells=surface + extra,
        )

    def heightmap_only(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
    ) -> list[MapCell]:
        pole_field = run_pole_resolve_pass(world, locations, padding)
        return run_heightmap_pass(world, locations, pole_field, padding)

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
        trigger: RecalcTrigger,
    ) -> list[MapCell]:
        """
        Recalc hook for future DAG node — re-runs anchor collect + weather, keeps z/terrain.
        """
        _ = trigger
        return self.apply_weather_only(world, locations, heightmap_cells)

    def _non_surface_anchor_cells(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> list[MapCell]:
        from app.application.worldData.generators.climate.locations import static_map_anchors
        from app.application.worldData.generators.climate.terrainZ import z_to_terrain

        uid_map     = {loc.location_uid: loc for loc in locations}
        terrain_set = {
            t["system_terrain"] for t in (world.terrain_registry or []) if "system_terrain" in t
        }
        extra: list[MapCell] = []
        for anchor in static_map_anchors(locations):
            if anchor.map_z == 0:
                continue
            climate_zone = self._climate.resolve_climate(world, uid_map, anchor)
            temp, rainfall = self._climate.weather_at_elevation(world, climate_zone, anchor.map_z)
            extra.append(MapCell(
                world_uid=world.world_uid,
                x=anchor.map_x,
                y=anchor.map_y,
                z=anchor.map_z,
                system_terrain=z_to_terrain(anchor.map_z, terrain_set),
                temperature_base=temp,
                rainfall=rainfall,
                location_uid=anchor.location_uid,
            ))
        return extra
