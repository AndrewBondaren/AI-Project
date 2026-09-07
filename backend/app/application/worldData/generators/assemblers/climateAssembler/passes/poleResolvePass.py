from app.application.worldData.generators.climate.poleResolve import resolve_pole_field
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
from app.application.worldData.generators.coordinates import map_cell_fine_span
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def run_pole_resolve_pass(
    world: World,
    locations: list[NamedLocation],
) -> ClimatePoleField:
    """Pass 0: manual climate_pole (max 1) or autoresolve N≥1 poles."""
    cell_m = map_cell_fine_span(world)
    bbox   = grid_bbox_from_locations(world, locations)
    return resolve_pole_field(world, locations, cell_m, bbox)
