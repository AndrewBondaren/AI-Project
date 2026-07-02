from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.terrainZ import z_to_terrain
from app.application.worldData.generators.terrain.passes.columnFillPass import (
    run_column_fill,
    run_column_fill_single,
)
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class TerrainGeneratorService:
    """
    Pure terrain skeleton generator — no climate fields on generate_surface.
    Climate: separate pass via ClimateOrchestratorService (DAG / materialization queue).

    Pole field is **caller-provided** (MapCellService / map.py debug harness) — TR-1b.
    """

    def generate_surface(
        self,
        world: World,
        locations: list[NamedLocation],
        pole_field: ClimatePoleField,
    ) -> list[MapCell]:
        heightmap = run_surface_pass(world, locations, pole_field)
        if heightmap is None:
            return []
        n_eff = run_gap_analysis(world, heightmap)
        return run_column_fill(world, heightmap, n_eff)

    def generate_surface_chunk(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap: SurfaceHeightmap,
        n_eff: dict[tuple[int, int], int],
        rect: ColumnRect,
    ) -> list[MapCell]:
        return run_column_fill(world, heightmap, n_eff, rect=rect)

    def build_surface_heightmap(
        self,
        world: World,
        locations: list[NamedLocation],
        pole_field: ClimatePoleField,
    ) -> tuple[SurfaceHeightmap | None, dict[tuple[int, int], int]]:
        heightmap = run_surface_pass(world, locations, pole_field)
        if heightmap is None:
            return None, {}
        return heightmap, run_gap_analysis(world, heightmap)

    def generate_z_slice(
        self,
        world: World,
        locations: list[NamedLocation],
        pole_field: ClimatePoleField,
        gx: int,
        gy: int,
        z_lo: int,
        z_hi: int,
    ) -> list[MapCell]:
        heightmap, n_eff = self.build_surface_heightmap(
            world, locations, pole_field,
        )
        if heightmap is None or (gx, gy) not in heightmap.surface_z:
            return []
        return run_column_fill_single(world, heightmap, n_eff, gx, gy, z_lo, z_hi)

    def generate_minimal(
        self,
        world: World,
        location: NamedLocation,
        uid_map: dict[str, NamedLocation] | None = None,
    ) -> list[MapCell]:
        from app.application.worldData.generators.climate import ClimateGeneratorService
        from app.application.jsonValidation import terrain_system_keys

        climate     = ClimateGeneratorService()
        terrain_set = terrain_system_keys(world)
        loc_map     = uid_map or {location.location_uid: location}

        x = location.map_x if location.map_x is not None else 0
        y = location.map_y if location.map_y is not None else 0
        z = location.map_z if location.map_z is not None else 0

        climate_zone   = climate.resolve_climate(world, loc_map, location)
        temp, rainfall = climate.weather_at_elevation(world, climate_zone, z)

        return [MapCell(
            world_uid=world.world_uid,
            x=x, y=y, z=z,
            system_terrain=z_to_terrain(z, terrain_set),
            temperature_base=temp,
            rainfall=rainfall,
            location_uid=location.location_uid,
        )]

    @staticmethod
    def iter_column_chunks(
        heightmap: SurfaceHeightmap,
        chunk_size: int = 32,
    ):
        """Row-major chunk rects covering heightmap bbox."""
        bbox = heightmap.bbox
        for y0 in range(bbox.y_min, bbox.y_max + 1, chunk_size):
            for x0 in range(bbox.x_min, bbox.x_max + 1, chunk_size):
                yield ColumnRect(
                    x_min=x0,
                    x_max=min(x0 + chunk_size - 1, bbox.x_max),
                    y_min=y0,
                    y_max=min(y0 + chunk_size - 1, bbox.y_max),
                )
