from app.application.worldData.generators.structure.structureElement import StructureElement
from app.db.models.mapCell import MapCell


def _door_cell(
    x: int, y: int, z: int, world_uid: str, building_uid: str, material: str,
    facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.DOOR,
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
        system_building_element=StructureElement.STAIRCASE,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _trapdoor_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.TRAPDOOR,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _void_cell(x: int, y: int, z: int, world_uid: str, building_uid: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.VOID,
        system_material=None,
        is_structural=False,
        location_uid=building_uid,
    )


def _open_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.ARCHWAY,
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
        system_building_element=StructureElement.STAIR_ANCHOR,
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
        system_building_element=StructureElement.STAIR_FLOOR,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
        system_facing=facing,
    )


def _window_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.WINDOW,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _ladder_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.LADDER,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _floor_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.FLOOR,
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _roof_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.ROOF,
        system_material=material,
        is_structural=True,
        location_uid=building_uid,
    )


def _opening_cell(
    x: int, y: int, z: int,
    world_uid: str, building_uid: str,
    terrain_type: str, material: str,
    glass_material: str | None = None,
    system_facing: str | None = None,
) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=terrain_type,
        system_material=material,
        glass_material=glass_material,
        system_facing=system_facing,
        is_structural=False,
        location_uid=building_uid,
    )
