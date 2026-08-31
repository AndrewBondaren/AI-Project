"""Approach material table §5.1.2 and CITY_STRUCTURE stamp on a finished ray."""

from __future__ import annotations

from random import Random

from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThresholdKind,
)
from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import (
    ApproachForm,
    StreetApproach,
)
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.structureAssembler.structureContext import (
    StructureContext,
)
from app.application.worldData.generators.terrain.relief.geom.geomResolve import partition_height
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.dataModel.materials import DEFAULT_FLOOR_MATERIAL, DEFAULT_ROAD_MATERIAL
from app.dataModel.structure.enums.buildingElement import StructureElement
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

_ROAD = WorldTerrainRegistry.require_engine_terrain_key("road")


def approach_material(
    kind: AreaThresholdKind,
    *,
    world: World,
    skeleton: CitySkeleton,
    building: NamedLocation | None,
    context: StructureContext | None,
    rng: Random,
) -> str:
    if kind == AreaThresholdKind.DOOR:
        # TODO(C21): porch / tambour — нет геометрии в здании. Когда клетки
        # крыльца появятся, материал подъезда = context.porch_material.
        _ = context
        if building is not None and building.parent_floor_material:
            return building.parent_floor_material
        return resolve_material(
            world, "floor", skeleton.economic_tier, rng, DEFAULT_FLOOR_MATERIAL,
        )
    return resolve_material(
        world, "road", skeleton.economic_tier, rng, DEFAULT_ROAD_MATERIAL,
    )


def stamp_approach_cells(
    approach: StreetApproach,
    material: str,
    *,
    world: World,
    location_uid: str | None,
) -> list[MapCell]:
    if approach.form == ApproachForm.NONE or approach.length < 1 or not approach.ray:
        return []
    h = abs(int(approach.z_near) - int(approach.z_far))
    if h == 0:
        return []
    sign = 1 if approach.z_far >= approach.z_near else -1
    ray = approach.ray
    if approach.form == ApproachForm.STAIRS:
        n = min(h, len(ray))
        steps = tuple(1 for _ in range(n)) + tuple(0 for _ in range(len(ray) - n))
        element = StructureElement.STAIRCASE.value
    else:
        steps = partition_height(h, len(ray))
        element = StructureElement.FLOOR.value

    acc = 0
    cells: list[MapCell] = []
    for (x, y), step in zip(ray, steps):
        acc += step
        cells.append(MapCell(
            world_uid=world.world_uid,
            x=x,
            y=y,
            z=int(approach.z_near) + sign * acc,
            system_terrain=_ROAD,
            system_material=material,
            system_building_element=element,
            is_structural=True,
            location_uid=location_uid,
        ))
    return cells
