import logging
import random
from collections.abc import Set
from dataclasses import replace

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import (
    AreaSlot,
    height_from_levels,
    z_deep_from_levels,
)
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import AreaThresholdKind
from app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers import (
    plan_area_barrier_cells,
    should_build_area_barrier,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.areaPaths import (
    build_area_paths,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.measureApproach import (
    DEFAULT_APPROACH_MAX_K,
    measure_street_approach,
    peek_abutting_street_z,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.resolveThreshold import (
    resolve_threshold,
)
from app.application.worldData.generators.assemblers.areaAssembler.planner.stampApproach import (
    approach_material,
    stamp_approach_cells,
)
from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import (
    ApproachForm,
    StreetApproach,
)
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.structureAssembler.buildingAssembler import (
    BuildingAssembler,
)
from app.application.worldData.generators.assemblers.structureAssembler.structureContext import (
    StructureContext,
)
from app.application.worldData.generators.coordinates.approachZ import clamp_near_z_to_45
from app.application.worldData.generators.coordinates.columnSurface import (
    column_surface,
    median_surface_z,
)
from app.application.worldData.generators.structure.layoutTranslate import translate_layout
from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
    rebind_layout_to_building,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.materials import DEFAULT_FLOOR_MATERIAL, DEFAULT_WALL_MATERIAL
from app.dataModel.structure.building.buildingLayoutTemplate import (
    BuildingLayoutTemplate,
    plot_has_building,
)
from app.dataModel.structure.enums.passageType import PassageType
from app.application.worldData.generators.structure.cellFactory import _floor_cell
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

Coord = tuple[int, int]


def derive_structure_context(
    template:      BuildingLayoutTemplate,
    city_skeleton: CitySkeleton,
    slot:          AreaSlot,
    terrain_cells: list[MapCell] | None,
    *,
    ground_z:      int,
) -> StructureContext:
    """
    v1: default_structure_context из шаблона + facing участка.
    ground_z = building.map_z после clamp. terrain_cells читает envelope на place.
    """
    _ = city_skeleton
    if terrain_cells:
        logger.debug(
            "derive_structure_context | terrain_columns=%d ground_z=%d",
            len(terrain_cells),
            ground_z,
        )
    ctx = template.default_structure_context
    return StructureContext(
        foundation_type=ctx.foundation_type,
        roof_type=ctx.roof_type,
        facing=slot.facing,
        foundation_depth=ctx.foundation_depth,
        ground_z=ground_z,
        foundation_material=ctx.foundation_material,
        roof_material=ctx.roof_material,
        porch_material=ctx.porch_material,
        porch_has_roof=ctx.porch_has_roof,
    )


def _runtime_footprint(
    template: BuildingLayoutTemplate,
    cached_layout: StructureLayout | None,
) -> OccupiedFootprint | None:
    if cached_layout is not None and cached_layout.occupied_footprint is not None:
        return cached_layout.occupied_footprint
    spec = template.occupied_footprint
    if spec is None:
        return None
    return OccupiedFootprint(
        min_x=spec.min_x,
        min_y=spec.min_y,
        width=spec.width,
        depth=spec.depth,
    )


def _cache_has_rooms(cached_layout: StructureLayout | None) -> bool:
    return cached_layout is not None and bool(cached_layout.rooms)


def _shell_layout(
    fp: OccupiedFootprint,
    bx: int,
    by: int,
    map_z: int,
    world: World,
    building: NamedLocation,
) -> StructureLayout:
    """Floor cells for the declared building bbox. Not rooms / small outbuildings."""
    material = building.parent_floor_material or DEFAULT_FLOOR_MATERIAL
    x0 = bx + fp.min_x
    y0 = by + fp.min_y
    cells = [
        _floor_cell(
            x0 + dx, y0 + dy, map_z,
            world.world_uid, building.location_uid, material,
        )
        for dx in range(fp.width)
        for dy in range(fp.depth)
    ]
    return StructureLayout(
        cells=cells,
        levels=[],
        passages=[],
        rooms=[],
        occupied_footprint=fp,
    )


def _footprint_cells(fp: OccupiedFootprint, bx: int, by: int) -> list[Coord]:
    x0 = bx + fp.min_x
    y0 = by + fp.min_y
    return [
        (x, y)
        for x in range(x0, x0 + fp.width)
        for y in range(y0, y0 + fp.depth)
    ]


def _entry_xy_world(
    cached_layout: StructureLayout | None,
    bx: int,
    by: int,
) -> Coord | None:
    if cached_layout is None:
        return None
    for passage in cached_layout.passages:
        if passage.from_level_uid is not None:
            continue
        pt = PassageType.from_wire(passage.system_passage_type)
        if pt == PassageType.MAIN_ENTRANCE:
            return (passage.to_x + bx, passage.to_y + by)
    return None


def _none_approach(z_near: int, z_far: int) -> StreetApproach:
    return StreetApproach(
        ray=(),
        length=0,
        z_far=z_far,
        z_near=z_near,
        theta_rad=0.0,
        form=ApproachForm.NONE,
    )


class StructureAreaAssembler:

    def assemble(
        self,
        world:          World,
        slot:           AreaSlot,
        template:       BuildingLayoutTemplate,
        city_skeleton:  CitySkeleton,
        terrain_cells:  list[MapCell] | None = None,
        *,
        street_xy:      Set[Coord] = frozenset(),
        cached_layout:  StructureLayout | None = None,
        building_x:     int | None = None,
        building_y:     int | None = None,
    ) -> AreaLayout:
        bx = building_x if building_x is not None else (
            min(c[0] for c in slot.cells) if slot.cells else 0
        )
        by = building_y if building_y is not None else (
            min(c[1] for c in slot.cells) if slot.cells else 0
        )

        logger.info(
            "StructureAreaAssembler | template=%s facing=%s slot_cells=%d cached=%s origin=(%d,%d)",
            template.system_name,
            slot.facing,
            len(slot.cells),
            cached_layout is not None,
            bx,
            by,
        )

        surface = column_surface(terrain_cells)
        fallback_z = slot.ground_z
        want_building = plot_has_building(template)

        rng = random.Random(f"{world.world_uid}_{bx}_{by}_barrier")
        has_barrier = should_build_area_barrier(template, rng)
        entry_xy = _entry_xy_world(cached_layout, bx, by) if want_building else None

        fp = _runtime_footprint(template, cached_layout)
        fp_cells: list[Coord] = _footprint_cells(fp, bx, by) if fp is not None else []
        threshold = resolve_threshold(
            slot,
            has_barrier=has_barrier,
            entry_xy=entry_xy,
            house_cells=fp_cells if want_building else None,
        )
        threshold = replace(
            threshold,
            z=median_surface_z(threshold.cells, surface, fallback_z),
        )

        yard_xy = list(slot.cells)
        if fp_cells:
            fp_set = set(fp_cells)
            yard_only = [c for c in slot.cells if c not in fp_set]
            if yard_only:
                yard_xy = yard_only
        slot.ground_z = median_surface_z(yard_xy, surface, fallback_z)

        building = None
        if want_building:
            building = self._place_building(
                world, slot, template, bx, by, fp_cells, surface,
            )

        origin = threshold.cells[0] if threshold.cells else (bx, by)
        z_near = int(building.map_z) if building is not None else threshold.z
        peek_z = peek_abutting_street_z(origin, slot.facing, street_xy, surface)
        if peek_z is None or slot.ground_z == peek_z:
            approach = _none_approach(z_near, peek_z if peek_z is not None else z_near)
        else:
            approach = measure_street_approach(
                origin, slot.facing, z_near, street_xy, surface,
                max_k=DEFAULT_APPROACH_MAX_K,
            )

        if (
            approach.form != ApproachForm.NONE
            and approach.length >= 1
            and abs(approach.z_near - approach.z_far) > approach.length
        ):
            clamped = clamp_near_z_to_45(
                z_near, approach.z_far, approach.length,
            )
            if building is not None:
                building.map_z = clamped
            else:
                threshold = replace(threshold, z=clamped)
            z_near = clamped
            approach = measure_street_approach(
                origin, slot.facing, z_near, street_xy, surface,
                max_k=DEFAULT_APPROACH_MAX_K,
            )

        building_layout: StructureLayout | None = None
        context: StructureContext | None = None
        if building is not None:
            context = derive_structure_context(
                template, city_skeleton, slot, terrain_cells,
                ground_z=int(building.map_z),
            )
            if _cache_has_rooms(cached_layout):
                building_layout = translate_layout(
                    cached_layout, bx, by, int(building.map_z),
                )
            elif fp is not None:
                building_layout = _shell_layout(
                    fp, bx, by, int(building.map_z), world, building,
                )
            else:
                building_layout = StructureLayout(
                    cells=[], levels=[], passages=[], rooms=[],
                )
            building_layout = BuildingAssembler.attach_envelope(
                world, building, building_layout, context, terrain_cells,
            )
            building_layout = rebind_layout_to_building(building_layout, building)

        door_xy = entry_xy
        yard_approach = None
        if (
            building is not None
            and threshold.kind != AreaThresholdKind.DOOR
            and door_xy is not None
        ):
            yard_approach = measure_street_approach(
                door_xy,
                slot.facing,
                int(building.map_z),
                set(threshold.cells),
                surface,
                max_k=DEFAULT_APPROACH_MAX_K,
            )

        loc_uid = building.location_uid if building is not None else None
        material = approach_material(
            threshold.kind,
            world=world,
            skeleton=city_skeleton,
            building=building,
            context=context,
            rng=rng,
        )
        yard_cells = stamp_approach_cells(
            approach, material, world=world, location_uid=loc_uid,
        )
        if yard_approach is not None:
            yard_cells = yard_cells + stamp_approach_cells(
                yard_approach, material, world=world, location_uid=loc_uid,
            )

        connection_nodes, connection_edges = build_area_paths(
            world_uid=world.world_uid,
            threshold=threshold,
            approach=approach,
            facing=slot.facing,
            building=building,
            door_xy=door_xy,
            yard_approach=yard_approach,
        )

        barrier_cells = self._build_barrier(
            world, slot, template, building, city_skeleton, rng,
        )

        levels = building_layout.levels if building_layout is not None else ()
        slot.height = height_from_levels(slot.ground_z, levels)
        slot.z_deep = z_deep_from_levels(slot.ground_z, levels)

        return AreaLayout(
            slot=slot,
            threshold=threshold,
            approach=approach,
            building_location=building,
            building_layout=building_layout,
            barrier_cells=barrier_cells,
            yard_cells=yard_cells,
            connection_nodes=connection_nodes,
            connection_edges=connection_edges,
        )

    def _place_building(
        self,
        world:     World,
        slot:      AreaSlot,
        template:  BuildingLayoutTemplate,
        map_x:     int,
        map_y:     int,
        fp_cells:  list[Coord],
        surface:   dict[Coord, int],
    ) -> NamedLocation:
        template_name = template.system_name
        map_z = median_surface_z(fp_cells, surface, slot.ground_z)
        return NamedLocation(
            location_uid=f"{world.world_uid}-{template_name}-{map_x}-{map_y}",
            world_uid=world.world_uid,
            display_name=template.display_name,
            system_location_type="building",
            created_at="2026-01-01T00:00:00",
            map_x=map_x,
            map_y=map_y,
            map_z=map_z,
            system_template_uid=template_name,
            parent_wall_material=DEFAULT_WALL_MATERIAL,
            parent_floor_material=DEFAULT_FLOOR_MATERIAL,
        )

    def _build_barrier(
        self,
        world:         World,
        slot:          AreaSlot,
        template:      BuildingLayoutTemplate,
        building:      NamedLocation | None,
        city_skeleton: CitySkeleton,
        rng:           random.Random,
    ) -> list[MapCell]:
        return plan_area_barrier_cells(
            world, slot, template, building, city_skeleton, rng,
        )
