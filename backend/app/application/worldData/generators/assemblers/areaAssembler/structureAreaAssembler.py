import logging
import random

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers import structureAssembler as _structure_assemblers  # noqa: F401
from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.structureContext import StructureContext
from app.application.worldData.generators.structure.layoutTranslate import translate_layout
from app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers import (
    plan_area_barrier_cells,
)
from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
    rebind_layout_to_building,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def derive_structure_context(
    template:      dict,
    city_skeleton: CitySkeleton,
    slot:          AreaSlot,
    terrain_cells: list[MapCell] | None,
) -> StructureContext:
    """
    v1: default_structure_context из шаблона + facing/ground_z участка.
    Полный алгоритм terrain/style — отложен (tz_assembler_hierarchy §7.8).
    """
    _ = (city_skeleton, terrain_cells)
    defaults = template.get("default_structure_context") or {}
    return StructureContext(
        foundation_type=defaults.get("foundation_type", "slab"),
        roof_type=defaults.get("roof_type", "gable"),
        facing=slot.facing,
        foundation_depth=int(defaults.get("foundation_depth", 1)),
        ground_z=slot.ground_z,
        foundation_material=defaults.get("foundation_material"),
        roof_material=defaults.get("roof_material"),
        porch_material=defaults.get("porch_material"),
        porch_has_roof=bool(defaults.get("porch_has_roof", False)),
    )


class StructureAreaAssembler:

    def assemble(
        self,
        world:          World,
        slot:           AreaSlot,
        template:       dict,
        city_skeleton:  CitySkeleton,
        terrain_cells:  list[MapCell] | None = None,
        cached_layout:  StructureLayout | None = None,
        building_x:     int | None = None,
        building_y:     int | None = None,
    ) -> AreaLayout:
        bx = building_x if building_x is not None else (min(c[0] for c in slot.cells) if slot.cells else 0)
        by = building_y if building_y is not None else (min(c[1] for c in slot.cells) if slot.cells else 0)

        logger.info(
            "StructureAreaAssembler | template=%s facing=%s slot_cells=%d cached=%s origin=(%d,%d)",
            template.get("system_name", "?"),
            slot.facing,
            len(slot.cells),
            cached_layout is not None,
            bx,
            by,
        )

        building = self._place_building(world, slot, template, bx, by)

        if cached_layout is not None:
            building_layout = translate_layout(cached_layout, bx, by)
        else:
            context = derive_structure_context(template, city_skeleton, slot, terrain_cells)
            structure_type = template.get("structure_type", "building")
            assembler = ASSEMBLER_REGISTRY.get(structure_type)
            building_layout = assembler.assemble(
                world, building, template, context, terrain_cells,
            )

        building_layout = rebind_layout_to_building(building_layout, building)

        barrier_cells = self._build_barrier(
            world, slot, template, building, city_skeleton,
        )

        return AreaLayout(
            building_location=building,
            building_layout=building_layout,
            barrier_cells=barrier_cells,
        )

    def _place_building(
        self,
        world:    World,
        slot:     AreaSlot,
        template: dict,
        map_x:    int,
        map_y:    int,
    ) -> NamedLocation:
        """v1: origin здания = anchor bin-packing (building_x/y)."""
        _ = slot
        return NamedLocation(
            location_uid=f"{world.world_uid}-{template.get('system_name', 'building')}-{map_x}-{map_y}",
            world_uid=world.world_uid,
            display_name=template.get("display_name", template.get("system_name", "Building")),
            system_location_type="building",
            created_at="2026-01-01T00:00:00",
            map_x=map_x,
            map_y=map_y,
            map_z=slot.ground_z,
            parent_wall_material="stone",
            parent_floor_material="wood",
        )

    def _build_barrier(
        self,
        world:         World,
        slot:          AreaSlot,
        template:      dict,
        building:      NamedLocation,
        city_skeleton: CitySkeleton,
    ) -> list[MapCell]:
        rng = random.Random(f"{building.location_uid}_barrier")
        return plan_area_barrier_cells(
            world, slot, template, building, city_skeleton, rng,
        )
