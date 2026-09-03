import random

from app.application.jsonValidation import connection_types
from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.districtAssembler.planner.areaSlots import (
    footprint_fits_rect,
    make_area_slot,
    origin_in_reservation,
    placements_from_reservations,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.frontage import (
    add_alleys,
    apply_frontage,
    plot_cells,
    touching_street_xy,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.barrierInset import (
    inner_bbox_for_slot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.corridor import (
    corridor_rects_from_entries,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.lattice import (
    district_step,
    make_lattice,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.pass1 import (
    run_pass1,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.pass2 import (
    holes_after_frame,
    run_pass2,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.tokens import (
    build_tokens,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    StreetFrameContext,
)
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    packing_info,
    packing_warning,
)
from app.application.worldData.generators.coordinates.columnSurface import column_surface
from app.application.worldData.generators.road.districtRoadGenerator import DistrictRoadGenerator
from app.application.worldData.generators.road.streetCells import (
    rasterize_edges_xy,
    rasterize_street_xy,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.settlement.district.districtConnection import primary_or_default
from app.dataModel.spatial.facing import Facing
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def _as_cache(layout_cache: BuildingLayoutCache | dict[str, StructureLayout] | None) -> BuildingLayoutCache:
    if layout_cache is None:
        return BuildingLayoutCache()
    if isinstance(layout_cache, BuildingLayoutCache):
        return layout_cache
    return BuildingLayoutCache.from_south_map(layout_cache)


class DistrictAssembler:

    def assemble(
        self,
        world:           World,
        slot:            DistrictSlot,
        city_skeleton:   CitySkeleton,
        terrain_cells:   list[MapCell] | None = None,
        layout_cache:    BuildingLayoutCache | dict[str, StructureLayout] | None = None,
        settlement_uid:  str | None = None,
    ) -> DistrictLayout:
        template = slot.district_template
        district = template.system_name
        primary = primary_or_default(template)
        cache = _as_cache(layout_cache)
        settlement_uid = settlement_uid or world.world_uid
        rng = random.Random(
            f"{world.world_uid}_{settlement_uid}_{slot.origin_x}_{slot.origin_y}_{district}",
        )

        inner, _widths, _reason = inner_bbox_for_slot(slot, world)
        step = district_step(slot, city_skeleton)
        lattice = make_lattice(inner, step)
        corridor, _ = corridor_rects_from_entries(slot, inner)
        tokens = build_tokens(slot, cache, world, city_skeleton)
        pass1, leftover1, occupied = run_pass1(slot, inner, lattice, tokens, corridor)
        _ = leftover1

        surface = column_surface(terrain_cells)
        frame = StreetFrameContext(
            inner=inner,
            step=step,
            blocked_rects=tuple(r.rect_xy for r in pass1),
            corridor_rects=corridor,
        )
        nodes, edges = self._plan_streets(
            slot, city_skeleton, world, surface, frame=frame,
        )
        empty_holes = holes_after_frame(lattice, occupied)
        packing_info(
            district, "frame",
            block_size=step,
            empty_modules=len(empty_holes),
            inner=inner.as_rect(),
            pass1=len(pass1),
            nodes=len(nodes),
            edges=len(edges),
        )

        pass2, leftover2 = run_pass2(slot, tokens, empty_holes)
        _ = leftover2
        reservations = pass1 + pass2
        placements = placements_from_reservations(
            reservations, cache, world, city_skeleton, slot.ground_z,
        )

        add_alleys(slot, placements, nodes, edges, world.world_uid)

        plot_mask: set[tuple[int, int]] = set()
        for placement in placements:
            plot_mask |= plot_cells(placement)

        edge_xy = rasterize_edges_xy(nodes, edges)
        street_xy = rasterize_street_xy(nodes, edges) - plot_mask
        packing_info(
            district, "graph",
            nodes=len(nodes), edges=len(edges),
            street_xy=len(street_xy), plots=len(plot_mask),
        )

        known = connection_types(world).keys() | WorldConnectionTypeRegistry.canonical_engine().keys()
        apply_frontage(
            placements, nodes, edges, edge_xy, street_xy,
            slot, city_skeleton, known, rng, settlement_uid,
        )

        for placement in placements:
            facing = placement.area_slot.facing
            layout = cache.ensure(world, placement.template, facing, district=district)
            res = placement.reservation
            if layout is None or layout.occupied_footprint is None or res is None:
                continue
            fp = layout.occupied_footprint
            bx, by = origin_in_reservation(fp, res.rect_xy)
            if not footprint_fits_rect(fp, res.rect_xy, bx, by):
                packing_warning(
                    district, "cache",
                    system_name=placement.template.system_name,
                    facing=facing.value,
                    reason="footprint_miss_reservation",
                )
                continue
            placement.building_x = bx
            placement.building_y = by
            placement.area_slot = make_area_slot(
                fp, bx, by, facing, fallback_z=slot.ground_z,
            )

        packing_info(
            district, "area_slots",
            area_slots=len(placements),
            street_xy=len(street_xy),
            connection_type=primary.connection_type,
            street_layout=template.street_layout or StreetLayout.GRID.value,
        )

        from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import (
            StructureAreaAssembler,
        )

        area_assembler = StructureAreaAssembler()
        area_layouts: list[AreaLayout] = []
        for placement in placements:
            local_street = touching_street_xy(plot_cells(placement), street_xy)
            cached = cache.get(
                placement.template.system_name,
                placement.area_slot.facing,
            )
            if cached is None:
                cached = cache.get(placement.template.system_name, Facing.SOUTH)
            packing_info(
                district, "area",
                template=placement.template.system_name,
                facing=placement.area_slot.facing.value,
                touching=len(local_street),
            )
            layout = area_assembler.assemble(
                world,
                placement.area_slot,
                placement.template,
                city_skeleton,
                terrain_cells,
                street_xy=local_street,
                cached_layout=cached,
                building_x=placement.building_x,
                building_y=placement.building_y,
            )
            area_layouts.append(layout)

        return DistrictLayout(
            slot=slot,
            area_layouts=area_layouts,
            connection_nodes=nodes,
            connection_edges=edges,
        )

    def _plan_streets(
        self,
        slot:          DistrictSlot,
        city_skeleton: CitySkeleton,
        world:         World,
        surface:       dict[tuple[int, int], int] | None = None,
        frame:         StreetFrameContext | None = None,
    ) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
        generator = DistrictRoadGenerator()
        rng = random.Random(f"{slot.origin_x}_{slot.origin_y}")
        return generator.generate(
            slot, city_skeleton, world, rng, surface=surface, frame=frame,
        )
