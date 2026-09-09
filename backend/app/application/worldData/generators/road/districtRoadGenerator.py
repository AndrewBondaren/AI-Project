"""
DistrictRoadGenerator — основной генератор улиц района.

Читает street_layout и connections из district_template,
делегирует в соответствующий layout-генератор.

Порядок:
  1. through_road-коридоры (жёсткие ограничения из entry_nodes) — в gridLayout
  2. Внутренняя сетка вокруг коридоров
  3. entry_point-узлы подключаются к ближайшему узлу сетки
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.road.layouts.culDeSacLayout import generate_cul_de_sac
from app.application.worldData.generators.road.layouts.courtyardLayout import generate_courtyard
from app.application.worldData.generators.road.layouts.gridLayout import generate_grid
from app.application.worldData.generators.road.layouts.organicLayout import generate_organic
from app.application.worldData.generators.road.layouts.radialLayout import generate_radial
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    StreetFrameContext,
)
from app.dataModel.settlement.district.districtConnection import street_classes_for
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.application.worldData.generators.road.connectionPolicy import paint_for_connection
from app.dataModel.settlement.enums.districtStreetRole import DistrictStreetRole
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.world import World

logger = logging.getLogger(__name__)

_LAYOUT_FN = {
    StreetLayout.GRID:       generate_grid,
    StreetLayout.ORGANIC:    generate_organic,
    StreetLayout.RADIAL:     generate_radial,
    StreetLayout.CUL_DE_SAC: generate_cul_de_sac,
    StreetLayout.COURTYARD:  generate_courtyard,
}


@dataclass
class DistrictStreetGraph:
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]
    edge_roles: dict[str, DistrictStreetRole] = field(default_factory=dict)


class DistrictRoadGenerator:

    def generate(
        self,
        slot:      DistrictSlot,
        skeleton:  CitySkeleton,
        world:     World,
        rng:       random.Random | None = None,
        surface:   dict[tuple[int, int], int] | None = None,
        frame:     StreetFrameContext | None = None,
    ) -> DistrictStreetGraph:
        if rng is None:
            rng = random.Random()

        template      = slot.district_template
        street_layout = StreetLayout.for_generator(template.street_layout)
        classes       = street_classes_for(template)
        fill          = paint_for_connection(classes.fill, world=world)
        spine         = paint_for_connection(classes.spine, world=world)

        fn = _LAYOUT_FN.get(street_layout)
        if fn is None:
            raise ValueError(f"Неизвестный street_layout: {street_layout.value!r}")

        logger.info(
            "DistrictRoadGenerator | layout=%s fill=%s spine=%s sidewalk_fill=%s"
            " sidewalk_spine=%s origin=(%d,%d) size=%dx%d skipped_roles=%s",
            street_layout.value, fill.connection_type, spine.connection_type,
            fill.has_sidewalk, spine.has_sidewalk,
            slot.origin_x, slot.origin_y, slot.width_fine, slot.depth_fine,
            classes.skipped_roles,
        )

        if street_layout == StreetLayout.GRID:
            nodes, edges, edge_roles = generate_grid(
                slot, skeleton, world.world_uid, fill, spine,
                rng, surface, frame=frame,
            )
            return DistrictStreetGraph(nodes=nodes, edges=edges, edge_roles=edge_roles)

        nodes, edges = fn(
            slot, skeleton, world.world_uid, fill.connection_type, fill.lanes_per_side,
            fill.has_sidewalk, rng,
            surface,
        )
        return DistrictStreetGraph(nodes=nodes, edges=edges)
