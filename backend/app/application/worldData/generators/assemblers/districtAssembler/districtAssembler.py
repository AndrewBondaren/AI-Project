import logging
import random

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import (
    StructureAreaAssembler,
)
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.districtAssembler.planner.areaSlots import (
    plan_area_placements,
)
from app.application.worldData.generators.road.districtRoadGenerator import DistrictRoadGenerator
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)


class DistrictAssembler:

    def assemble(
        self,
        world:          World,
        slot:           DistrictSlot,
        city_skeleton:  CitySkeleton,
        terrain_cells:  list[MapCell] | None = None,
        layout_cache:   dict[str, StructureLayout] | None = None,
    ) -> DistrictLayout:
        template = slot.district_template
        connections = template.get("connections") or []
        primary = connections[0] if connections else {}
        cache = layout_cache or {}

        rng = random.Random(
            f"{world.world_uid}_{slot.origin_x}_{slot.origin_y}_{template.get('system_name', '')}",
        )
        placements = plan_area_placements(slot, cache, world, city_skeleton, rng)

        logger.info(
            "DistrictAssembler | template=%s district_type=%s origin=(%d,%d) size=%dx%d"
            " street_layout=%s algorithm=%s connection_type=%s sidewalk=%s"
            " area_slots=%d required_structures=%d",
            template.get("system_name", "?"),
            template.get("district_type", "?"),
            slot.origin_x,
            slot.origin_y,
            slot.width_m,
            slot.depth_m,
            template.get("street_layout") or "grid",
            "DistrictRoadGenerator",
            primary.get("connection_type") or "road",
            primary.get("sidewalk"),
            len(placements),
            len(slot.required_structures),
        )
        if slot.required_structures:
            for req in slot.required_structures:
                logger.info(
                    "DistrictAssembler required_structure | template=%s building=%s count=%s position=%s",
                    template.get("system_name", "?"),
                    req.get("building_template"),
                    req.get("count", 1),
                    req.get("position", "any"),
                )

        area_assembler = StructureAreaAssembler()
        area_layouts: list[AreaLayout] = []

        for placement in placements:
            template_name = placement.template.get("system_name", "")
            cached = cache.get(template_name)
            layout = area_assembler.assemble(
                world,
                placement.area_slot,
                placement.template,
                city_skeleton,
                terrain_cells,
                cached_layout=cached,
                building_x=placement.building_x,
                building_y=placement.building_y,
            )
            area_layouts.append(layout)

        nodes, edges = self._plan_streets(slot, city_skeleton, world)

        logger.info(
            "DistrictAssembler done | template=%s district_nodes=%d district_edges=%d area_layouts=%d",
            template.get("system_name", "?"),
            len(nodes),
            len(edges),
            len(area_layouts),
        )

        return DistrictLayout(
            area_layouts     = area_layouts,
            connection_nodes = nodes,
            connection_edges = edges,
        )

    def _plan_streets(
        self,
        slot:          DistrictSlot,
        city_skeleton: CitySkeleton,
        world:         World,
    ) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
        generator = DistrictRoadGenerator()
        rng       = random.Random(f"{slot.origin_x}_{slot.origin_y}")
        return generator.generate(slot, city_skeleton, world, rng)
