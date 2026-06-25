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
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

logger = logging.getLogger(__name__)

_LAYOUT_FN = {
    "grid":       generate_grid,
    "organic":    generate_organic,
    "radial":     generate_radial,
    "cul_de_sac": generate_cul_de_sac,
    "courtyard":  generate_courtyard,
}

# Дефолтный auto_sidewalk по типу дороги (если template не задаёт явно)
_AUTO_SIDEWALK: dict[str, bool] = {
    "road":    True,
    "highway": True,
}

# Дефолтное кол-во полос если не задано в connections[]
_DEFAULT_LANES: dict[str, int] = {
    "road":    1,
    "highway": 2,
}


class DistrictRoadGenerator:

    def generate(
        self,
        slot:      DistrictSlot,
        skeleton:  CitySkeleton,
        world_uid: str,
        rng:       random.Random | None = None,
    ) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
        if rng is None:
            rng = random.Random()

        template      = slot.district_template
        street_layout = template.get("street_layout") or "grid"
        connections   = template.get("connections") or []

        primary         = connections[0] if connections else {}
        connection_type = primary.get("connection_type") or "road"
        lanes_per_side  = primary.get("lanes_per_side") or _DEFAULT_LANES.get(connection_type, 1)

        sidewalk_decl = primary.get("sidewalk")
        has_sidewalk  = (
            sidewalk_decl
            if sidewalk_decl is not None
            else _AUTO_SIDEWALK.get(connection_type, False)
        )

        fn = _LAYOUT_FN.get(street_layout)
        if fn is None:
            raise ValueError(f"Неизвестный street_layout: {street_layout!r}")

        logger.info(
            "DistrictRoadGenerator | layout=%s type=%s lanes=%s sidewalk=%s origin=(%d,%d) size=%dx%d",
            street_layout, connection_type, lanes_per_side, has_sidewalk,
            slot.origin_x, slot.origin_y, slot.width_m, slot.depth_m,
        )

        return fn(slot, skeleton, world_uid, connection_type, lanes_per_side, has_sidewalk, rng)
