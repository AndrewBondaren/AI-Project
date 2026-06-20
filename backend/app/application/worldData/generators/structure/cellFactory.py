from app.db.models.mapCell import MapCell


def _door_cell(
    x: int, y: int, z: int, world_uid: str, building_uid: str, material: str,
    facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="door",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _stair_cell(
    x: int, y: int, z: int, world_uid: str, building_uid: str, material: str,
    facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="staircase",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _trapdoor_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="trapdoor",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _void_cell(x: int, y: int, z: int, world_uid: str, building_uid: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="void",
        system_material=None,
        is_structural=False,
        location_uid=building_uid,
    )


def _open_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="archway",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _stair_anchor_cell(
    x: int, y: int, z: int, world_uid: str, building_uid: str, material: str,
    facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="stair_anchor",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _stair_floor_cell(
    x: int, y: int, z: int, world_uid: str, building_uid: str, material: str,
    facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="stair_floor",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _window_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="window",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _ladder_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="ladder",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _floor_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="floor",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _opening_cell(
    x: int, y: int, z: int,
    world_uid: str, building_uid: str,
    terrain_type: str, material: str,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=terrain_type,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )
