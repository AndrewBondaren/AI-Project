from app.application.worldData.generators.assemblers.climateAssembler.climateSurfaceAssembler import (
    ClimateSurfaceAssembler,
    ClimateSurfaceResult,
)
from app.application.worldData.generators.assemblers.climateAssembler.types import ClimateRecalcRequest
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class ClimateOrchestratorService:
    """
    Facade for engine DAG nodes; map.py debug routes call the same methods — not the production entry point.

    Three processes (tz_climate.md § v2.3):
      1. full_surface / heightmap_only / apply_weather_only — eager generate
      2. recalculate(ClimateRecalcRequest) — partial update on existing heightmap
    Runtime weather: ClimateRuntimeAssembler (process 3).
    """

    def __init__(
        self,
        climate: ClimateGeneratorService | None = None,
        surface: ClimateSurfaceAssembler | None = None,
    ) -> None:
        self._climate = climate or ClimateGeneratorService()
        self._surface = surface or ClimateSurfaceAssembler(self._climate)

    def full_surface(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> list[MapCell]:
        return self._surface.assemble_full(world, locations).surface_cells

    def full_surface_detailed(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> ClimateSurfaceResult:
        return self._surface.assemble_full(world, locations)

    def heightmap_only(
        self,
        world: World,
        locations: list[NamedLocation],
    ) -> list[MapCell]:
        return self._surface.heightmap_only(world, locations)

    def apply_weather_only(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
        anchor_field: ClimateAnchorField | None = None,
        pole_field: ClimatePoleField | None = None,
    ) -> list[MapCell]:
        return self._surface.apply_weather_only(
            world,
            locations,
            heightmap_cells,
            pole_field=pole_field,
            anchor_field=anchor_field,
        )

    def apply_climate_pass(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
    ) -> list[MapCell]:
        return self._surface.apply_climate_pass(
            world, locations, heightmap_cells,
        )

    def recalculate(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
        request: ClimateRecalcRequest,
    ) -> list[MapCell]:
        return self._surface.recalculate(world, locations, heightmap_cells, request)
