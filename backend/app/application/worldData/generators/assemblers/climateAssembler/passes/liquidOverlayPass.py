from app.application.worldData.generators.climate.precipitation import liquid_precipitation_mult
from app.application.worldData.generators.climate.precipitation import resolve_world_precipitation_liquid
from app.application.jsonValidation import terrain_system_keys
from app.dataModel.hydrology.mapCellHydrology import cell_hydrology_liquid_candidate
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def run_liquid_overlay_pass(
    world: World,
    cells: list[MapCell],
) -> list[MapCell]:
    """
    Apply liquid_body on surface-top cells when hydrology marked liquid_candidate
    and temperature allows liquid phase (tz_terrain_hydrology.md U7, D HY-6).

    Does not use global z<=0. River beds already liquid_body from hydrology (U28)
    are left unchanged here — phase/material is a separate concern.
    """
    terrain_set = terrain_system_keys(world)
    if "liquid_body" not in terrain_set:
        return cells

    liquid = resolve_world_precipitation_liquid(world)

    surface_top: dict[tuple[int, int], MapCell] = {}
    for cell in cells:
        key = (cell.x, cell.y)
        prev = surface_top.get(key)
        if prev is None or cell.z > prev.z:
            surface_top[key] = cell

    result: list[MapCell] = []
    for cell in cells:
        top = surface_top.get((cell.x, cell.y))
        is_surface_top = (
            top is not None
            and cell.x == top.x
            and cell.y == top.y
            and cell.z == top.z
        )
        if not is_surface_top:
            result.append(cell)
            continue

        if cell.system_terrain == "liquid_body":
            result.append(cell)
            continue

        if (
            cell_hydrology_liquid_candidate(cell.hydrology)
            and cell.temperature_base is not None
            and liquid_precipitation_mult(cell.temperature_base, liquid, world.world_uid) > 0
        ):
            result.append(MapCell(
                world_uid=cell.world_uid,
                x=cell.x,
                y=cell.y,
                z=cell.z,
                system_terrain="liquid_body",
                system_building_element=cell.system_building_element,
                system_material=cell.system_material,
                is_structural=cell.is_structural,
                travel_modifier_override=cell.travel_modifier_override,
                system_danger_level_override=cell.system_danger_level_override,
                gap_width_override=cell.gap_width_override,
                temperature_base=cell.temperature_base,
                rainfall=cell.rainfall,
                location_uid=cell.location_uid,
                railing_sides=cell.railing_sides,
                system_facing=cell.system_facing,
                display_facing=cell.display_facing,
                glass_material=cell.glass_material,
                hydrology=cell.hydrology,
            ))
        else:
            result.append(cell)
    return result
