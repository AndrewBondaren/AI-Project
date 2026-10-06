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
    area_gate_cells,
    area_gate_transitions,
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
from app.application.worldData.generators.assemblers.buildingAssembler.buildingAssembler import (
    BuildingAssembler,
)
from app.application.worldData.generators.assemblers.buildingAssembler.structureContext import (
    StructureContext,
)
from app.application.worldData.context.locationScope import (
    area_context,
    building_context,
    empty_location_chain,
)
from app.application.worldData.ids import UidKind, entity_rng
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    area_uid as _area_uid,
    building_location_uid as _building_location_uid,
)
from app.application.worldData.generators.coordinates.approachZ import clamp_near_z_to_45
from app.application.worldData.generators.coordinates.columnSurface import (
    column_surface,
    median_surface_z,
)
from app.application.worldData.generators.structure.layoutTranslate import translate_layout
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
    plot_has_building,
)
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

Coord = tuple[int, int]


def derive_structure_context(
    world:         World,
    template:      PlotLayoutTemplate,
    city_skeleton: CitySkeleton,
    slot:          AreaSlot,
    terrain_cells: list[MapCell] | None,
    *,
    ground_z:      int,
    district_ctx:  LocationContext,
    area_uid:      str,
    building:      NamedLocation,
) -> StructureContext:
    """
    v1: тело участка (main_building), геометрия в авторском фрейме.
    ground_z = building.map_z на посадке. terrain_cells читает envelope.

    ``district_ctx`` — resolved district-scope cascade ctx; ``building``
    — NL-звено building-уровня (persisted row при перегенерации, иначе
    свежий in-memory NL из ``_place_building``). Effective tier всех
    structure-фаз — ``context.location_ctx.economic_tier`` (§4).
    """
    _ = city_skeleton
    if terrain_cells:
        logger.debug(
            "derive_structure_context | terrain_columns=%d ground_z=%d",
            len(terrain_cells),
            ground_z,
        )
    area_ctx = area_context(
        world, district_ctx, template, area_uid=area_uid,
    )
    body = template.main_building
    defaults = BuildingBodyTemplate.model_fields
    return StructureContext(
        foundation_type=(
            body.foundation_type
            if body is not None
            else defaults["foundation_type"].default
        ),
        roof_type=body.roof_type if body is not None else defaults["roof_type"].default,
        facing=None,
        foundation_depth=(
            body.foundation_depth
            if body is not None
            else defaults["foundation_depth"].default
        ),
        ground_z=ground_z,
        location_ctx=building_context(world, area_ctx, building),
        foundation_material=(
            body.foundation_material
            if body is not None
            else defaults["foundation_material"].default
        ),
        roof_material=(
            body.roof_material
            if body is not None
            else defaults["roof_material"].default
        ),
        porch_material=(
            body.porch_material
            if body is not None
            else defaults["porch_material"].default
        ),
        porch_has_roof=(
            body.porch_has_roof
            if body is not None
            else defaults["porch_has_roof"].default
        ),
    )


def _runtime_footprint(
    template: PlotLayoutTemplate,
) -> OccupiedFootprint | None:
    spec = template.occupied_footprint
    if spec is None:
        return None
    return OccupiedFootprint(
        min_x=spec.min_x,
        min_y=spec.min_y,
        width=spec.width,
        depth=spec.depth,
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
    layout: StructureLayout | None,
) -> Coord | None:
    if layout is None:
        return None
    for passage in layout.transitions:
        if passage.source.level_uid is not None:
            continue
        if passage.system_transition_type == TransitionType.MAIN_ENTRANCE:
            return (passage.destination.x, passage.destination.y)
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
        template:       PlotLayoutTemplate,
        city_skeleton:  CitySkeleton,
        terrain_cells:  list[MapCell] | None = None,
        *,
        structure_catalog: StructureCatalog,
        street_xy:      Set[Coord] = frozenset(),
        building_x:     int | None = None,
        building_y:     int | None = None,
        district_ctx:   LocationContext | None = None,
        district_uid:   str | None = None,
        existing_buildings: dict[str, NamedLocation] | None = None,
    ) -> AreaLayout:
        bx = building_x if building_x is not None else (
            min(c[0] for c in slot.cells) if slot.cells else 0
        )
        by = building_y if building_y is not None else (
            min(c[1] for c in slot.cells) if slot.cells else 0
        )

        logger.info(
            "StructureAreaAssembler | template=%s facing=%s slot_cells=%d origin=(%d,%d)",
            template.system_name,
            slot.facing,
            len(slot.cells),
            bx,
            by,
        )

        surface = column_surface(terrain_cells)
        fallback_z = slot.ground_z
        want_building = plot_has_building(template)

        rng = entity_rng(
            world.world_uid, UidKind.BARRIER,
            x=bx, y=by,
            **({"district": district_uid} if district_uid is not None else {}),
        )
        fp = _runtime_footprint(template)
        fp_cells: list[Coord] = _footprint_cells(fp, bx, by) if fp is not None else []

        yard_xy = list(slot.cells)
        if fp_cells:
            fp_set = set(fp_cells)
            yard_only = [c for c in slot.cells if c not in fp_set]
            if yard_only:
                yard_xy = yard_only
        slot.ground_z = median_surface_z(yard_xy, surface, fallback_z)

        building = None
        building_layout: StructureLayout | None = None
        context: StructureContext | None = None
        if want_building:
            slot_cells = list(slot.cells) or [(0, 0)]
            area_uid = (
                _area_uid(
                    world.world_uid, district_uid,
                    min(c[0] for c in slot_cells),
                    min(c[1] for c in slot_cells),
                    slot.facing,
                )
                if district_uid is not None
                else None
            )
            building = self._place_building(
                world, slot, template, bx, by, fp_cells, surface,
                area_uid=area_uid,
            )
            if area_uid is None:
                area_uid = f"{building.location_uid}#area"
            body = template.main_building
            structure = structure_catalog.resolve(body.structure)
            if structure is None:
                raise GenerationError(
                    f"Plot '{template.system_name}': structure '{body.structure}' not found"
                )
            link = building
            if existing_buildings:
                link = (
                    existing_buildings.get(building.location_uid) or building
                )
            context = derive_structure_context(
                world, template, city_skeleton, slot, terrain_cells,
                ground_z=int(building.map_z),
                district_ctx=(
                    district_ctx
                    if district_ctx is not None
                    else empty_location_chain(world, ScopeLevel.DISTRICT)
                ),
                area_uid=area_uid,
                building=link,
            )
            # §8.4 / M5: every new NL in the chain carries its effective
            # tier; a persisted authored stamp surfaces unchanged (the
            # persisted link wins the building scope). M9: the resolved
            # parent materials stamp the same way — the NL columns hold
            # the effective material for the assembler and LLM context.
            building = replace(
                building,
                system_economic_tier=context.location_ctx.economic_tier,
                parent_wall_material=context.location_ctx.wall_material,
                parent_floor_material=context.location_ctx.floor_material,
            )
            building_layout = BuildingAssembler().assemble(
                world, building, body, structure, context, terrain_cells,
            )

        barrier_cells = self._build_barrier(
            world, slot, template, building, city_skeleton, rng,
        )
        gates = area_gate_cells(barrier_cells)
        entry_xy = _entry_xy_world(building_layout)
        threshold = resolve_threshold(
            slot,
            has_barrier=bool(barrier_cells),
            gate_cells=[(cell.x, cell.y) for cell in gates],
            entry_xy=entry_xy,
            house_cells=fp_cells if want_building else None,
        )
        threshold = replace(
            threshold,
            z=gates[0].z if gates and threshold.kind == AreaThresholdKind.GATE
                else median_surface_z(threshold.cells, surface, fallback_z),
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
                building_layout = translate_layout(building_layout, 0, 0, clamped - z_near)
                building.map_z = clamped
                context = replace(context, ground_z=clamped)
            else:
                threshold = replace(threshold, z=clamped)
            z_near = clamped
            approach = measure_street_approach(
                origin, slot.facing, z_near, street_xy, surface,
                max_k=DEFAULT_APPROACH_MAX_K,
            )

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

        # The existing approach clamp can move a buildingless threshold in z.
        # Keep the physical opening at the finalized graph threshold elevation.
        if gates and threshold.kind == AreaThresholdKind.GATE:
            gate_xy = set(threshold.cells)
            barrier_cells = [replace(cell, z=threshold.z) if (cell.x, cell.y) in gate_xy else cell
                             for cell in barrier_cells]

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
            transitions=area_gate_transitions(world, slot, barrier_cells),
        )

    def _place_building(
        self,
        world:     World,
        slot:      AreaSlot,
        template:  PlotLayoutTemplate,
        map_x:     int,
        map_y:     int,
        fp_cells:  list[Coord],
        surface:   dict[Coord, int],
        *,
        area_uid:  str | None = None,
    ) -> NamedLocation:
        template_name = template.system_name
        map_z = median_surface_z(fp_cells, surface, slot.ground_z)
        # Single minting point of the building uid (DET-1 D4): the
        # canonical det-id when the district chain is known; the readable
        # fallback only stands in debug/standalone layouts.
        location_uid = (
            _building_location_uid(
                world.world_uid, area_uid, template_name, map_x, map_y,
            )
            if area_uid is not None
            else f"{world.world_uid}-{template_name}-{map_x}-{map_y}"
        )
        return NamedLocation(
            location_uid=location_uid,
            world_uid=world.world_uid,
            display_name=template.display_name,
            system_location_type="building",
            created_at="2026-01-01T00:00:00",
            map_x=map_x,
            map_y=map_y,
            map_z=map_z,
            system_template_uid=template_name,
        )

    def _build_barrier(
        self,
        world:         World,
        slot:          AreaSlot,
        template:      PlotLayoutTemplate,
        building:      NamedLocation | None,
        city_skeleton: CitySkeleton,
        rng:           random.Random,
    ) -> list[MapCell]:
        return plan_area_barrier_cells(
            world, slot, template, building, city_skeleton, rng,
        )
