from app.application.worldData.generators.assemblers.climateAssembler.climateSurfaceAssembler import (
    ClimateSurfaceAssembler,
    ClimateSurfaceResult,
)
from app.application.worldData.generators.assemblers.climateAssembler.types import RecalcTrigger
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class ClimateOrchestratorService:
    """
    Facade for admin API and future DAG nodes — no engine imports.
    Entry at any pass level (SettlementGeneratorService pattern).
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
        padding: int = 2,
    ) -> list[MapCell]:
        return self._surface.assemble_full(world, locations, padding).surface_cells

    def full_surface_detailed(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
    ) -> ClimateSurfaceResult:
        return self._surface.assemble_full(world, locations, padding)

    def heightmap_only(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
    ) -> list[MapCell]:
        return self._surface.heightmap_only(world, locations, padding)

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

    def recalculate(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap_cells: list[MapCell],
        trigger: RecalcTrigger,
    ) -> list[MapCell]:
        return self._surface.recalculate(world, locations, heightmap_cells, trigger)
