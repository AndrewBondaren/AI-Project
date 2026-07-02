"""
DistrictRoadGenerator — основной генератор улиц района.

Читает street_layout и connections из district_template,
делегирует в соответствующий layout-генератор.

Порядок:
  1. through_road-коридоры (жёсткие ограничения из entry_nodes) — в gridLayout
  2. Внутренняя сетка вокруг коридоров
  3. entry_point-узлы подключаются к ближайшему узлу сетки
"""
import logging
import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.road.layouts.culDeSacLayout import generate_cul_de_sac
from app.application.worldData.generators.road.layouts.courtyardLayout import generate_courtyard
from app.application.worldData.generators.road.layouts.gridLayout import generate_grid
from app.application.worldData.generators.road.layouts.organicLayout import generate_organic
from app.application.worldData.generators.road.layouts.radialLayout import generate_radial
from app.application.worldData.generators.road.connectionPolicy import (
    primary_connection,
    resolve_has_sidewalk,
    resolve_lanes_per_side,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.world import World

logger = logging.getLogger(__name__)

_LAYOUT_FN = {
    "grid":       generate_grid,
    "organic":    generate_organic,
    "radial":     generate_radial,
    "cul_de_sac": generate_cul_de_sac,
    "courtyard":  generate_courtyard,
}

class DistrictRoadGenerator:

    def generate(
        self,
        slot:      DistrictSlot,
        skeleton:  CitySkeleton,
        world:     World,
        rng:       random.Random | None = None,
    ) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
        if rng is None:
            rng = random.Random()

        template      = slot.district_template
        street_layout = template.get("street_layout") or "grid"

        primary         = primary_connection(template)
        connection_type = primary.connection_type
        lanes_per_side  = resolve_lanes_per_side(template, connection_type, world=world)
        has_sidewalk    = resolve_has_sidewalk(template, connection_type, world=world)

        fn = _LAYOUT_FN.get(street_layout)
        if fn is None:
            raise ValueError(f"Неизвестный street_layout: {street_layout!r}")

        logger.info(
            "DistrictRoadGenerator | layout=%s type=%s lanes=%s sidewalk=%s origin=(%d,%d) size=%dx%d",
            street_layout, connection_type, lanes_per_side, has_sidewalk,
            slot.origin_x, slot.origin_y, slot.width_m, slot.depth_m,
        )

        return fn(slot, skeleton, world.world_uid, connection_type, lanes_per_side, has_sidewalk, rng)
