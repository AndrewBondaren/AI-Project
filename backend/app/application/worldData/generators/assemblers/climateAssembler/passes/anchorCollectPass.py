from app.application.worldData.generators.climate.anchorAssign import auto_anchors_from_features
from app.application.worldData.generators.climate.anchorCollect import (
    build_merged_field,
    collect_manual_anchors,
)
from app.application.worldData.generators.climate.anchorDetect import (
    ProminenceScale,
    detect_terrain_features,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.generators.coordinates import cell_size_m


def run_anchor_collect_pass(
    world: World,
    locations: list[NamedLocation],
    heightmap_cells: list[MapCell],
    pole_field: ClimatePoleField,
) -> ClimateAnchorField:
    """Pass 2: local manual + terrain auto (zone from pole field), admin fallback."""
    cell_m   = cell_size_m(world)
    uid_map  = {loc.location_uid: loc for loc in locations}
    manual   = collect_manual_anchors(locations, cell_m)
    features = detect_terrain_features(
        heightmap_cells, world.world_uid, scale=ProminenceScale.METRIC,
    )
    auto     = auto_anchors_from_features(features, world, uid_map, pole_field)
    return build_merged_field(
        manual, auto, locations, cell_m,
        world=world,
        include_admin_fallback=pole_field.is_empty(),
    )
