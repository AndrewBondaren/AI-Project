from app.application.worldData.generators.climate.poleResolve import resolve_pole_field
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.assemblers.climateAssembler.passes.heightmapPass import (
    grid_bbox_from_locations,
)
from app.application.worldData.generators.coordinates import cell_size_m
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def run_pole_resolve_pass(
    world: World,
    locations: list[NamedLocation],
    padding: int = 2,
) -> ClimatePoleField:
    """Pass 0: manual climate_pole (max 1) or autoresolve N≥1 poles."""
    cell_m = cell_size_m(world)
    bbox   = grid_bbox_from_locations(locations, cell_m, padding)
    return resolve_pole_field(world, locations, cell_m, bbox)
