from app.application.worldData.generators.climate.terrainZ import z_to_terrain
from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService
from app.application.worldData.generators.climate import ClimateGeneratorService
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class TerrainGeneratorService:
    """
    Thin facade — delegates surface generation to ClimateOrchestratorService.
    Kept for admin API and existing engine lazy_terrain imports.
    """

    def __init__(
        self,
        orchestrator: ClimateOrchestratorService | None = None,
        climate_generator: ClimateGeneratorService | None = None,
    ) -> None:
        climate = climate_generator or ClimateGeneratorService()
        self._orchestrator = orchestrator or ClimateOrchestratorService(climate=climate)
        self._climate      = climate

    def generate_surface(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
    ) -> list[MapCell]:
        return self._orchestrator.full_surface(world, locations, padding)

    def generate_minimal(
        self,
        world: World,
        location: NamedLocation,
        uid_map: dict[str, NamedLocation] | None = None,
    ) -> list[MapCell]:
        terrain_reg = world.terrain_registry or []
        terrain_set = {t["system_terrain"] for t in terrain_reg if "system_terrain" in t}
        loc_map     = uid_map or {location.location_uid: location}

        x = location.map_x if location.map_x is not None else 0
        y = location.map_y if location.map_y is not None else 0
        z = location.map_z if location.map_z is not None else 0

        climate_zone   = self._climate.resolve_climate(world, loc_map, location)
        temp, rainfall = self._climate.weather_at_elevation(world, climate_zone, z)

        return [MapCell(
            world_uid=world.world_uid,
            x=x, y=y, z=z,
            system_terrain=z_to_terrain(z, terrain_set),
            temperature_base=temp,
            rainfall=rainfall,
            location_uid=location.location_uid,
        )]
