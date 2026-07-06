from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _weathered_cell(
    cell: MapCell,
    *,
    temperature_base: int,
    rainfall: int,
    location_uid: str | None,
) -> MapCell:
    """Preserve terrain skeleton fields; set climate scalars."""
    return MapCell(
        world_uid=cell.world_uid,
        x=cell.x,
        y=cell.y,
        z=cell.z,
        system_terrain=cell.system_terrain,
        system_building_element=cell.system_building_element,
        system_material=cell.system_material,
        is_structural=cell.is_structural,
        travel_modifier_override=cell.travel_modifier_override,
        system_danger_level_override=cell.system_danger_level_override,
        gap_width_override=cell.gap_width_override,
        temperature_base=temperature_base,
        rainfall=rainfall,
        location_uid=location_uid,
        railing_sides=cell.railing_sides,
        system_facing=cell.system_facing,
        display_facing=cell.display_facing,
        glass_material=cell.glass_material,
        hydrology=cell.hydrology,
    )


def run_cell_weather_pass(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    cells: list[MapCell],
    climate: ClimateGeneratorService | None = None,
) -> list[MapCell]:
    """Pass 3: pole + local tier sample, then temperature_base and rainfall."""
    svc     = climate or ClimateGeneratorService()
    uid_map = {loc.location_uid: loc for loc in locations}

    result: list[MapCell] = []
    for cell in cells:
        sample = svc.resolve_surface_sample(
            world, uid_map, pole_field, local_field, cell.x, cell.y,
        )
        temp, rainfall = svc.weather_at_elevation(
            world,
            sample.system_climate_zone,
            cell.z,
            sample.base_temperature_override,
        )
        result.append(_weathered_cell(
            cell,
            temperature_base=temp,
            rainfall=rainfall,
            location_uid=sample.zone_location_uid,
        ))
    return result
