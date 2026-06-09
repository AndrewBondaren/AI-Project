"""
Staircase builder — оркестратор.

Читает staircase_type из room definition, диспатчит к нужному builder-классу,
создаёт и возвращает LocationPassage.
"""
import logging
import uuid

from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase._straight  import StraightBuilder
from app.application.worldData.generators.structure.staircase._uShape    import UShapeBuilder
from app.application.worldData.generators.structure.staircase._spiral    import SpiralBuilder
from app.application.worldData.generators.structure.staircase._trapdoor  import TrapdoorBuilder
from app.application.worldData.generators.structure.staircase._base      import StaircaseBuilder
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_BUILDERS: dict[str, type[StaircaseBuilder]] = {
    "straight": StraightBuilder,
    "u_shape":  UShapeBuilder,
    "spiral":   SpiralBuilder,
    "trapdoor": TrapdoorBuilder,
}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def build_staircase(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    mat: str,
) -> LocationPassage | None:
    conn_label = f"{conn['from_room']}->{conn['to_room']}"

    going_underground = (fr.z_offset >= 0 and to.z_offset < 0)
    coming_up         = (fr.z_offset < 0  and to.z_offset >= 0)
    stair_type = "trapdoor" if (going_underground or coming_up) else getattr(to, "staircase_type", None)

    if stair_type not in _BUILDERS:
        logger.error("staircase %s: unknown staircase_type=%r", conn_label, stair_type)
        return None

    builder = _BUILDERS[stair_type](
        fr, to, fr_level, to_level, cells, world_uid, building_uid, mat, conn_label
    )

    logger.info("staircase %s: type=%s z_height=%d", conn_label, stair_type,
                abs(to_level.z - fr_level.z))

    try:
        fr_anchor, to_anchor = builder.build()
    except NotImplementedError:
        logger.error("staircase %s: %s not implemented", conn_label, stair_type)
        return None

    fx, fy = fr_anchor
    tx, ty = to_anchor
    passage_uid = _det_uuid(building_uid, "stair", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=fx,
        from_y=fy,
        to_level_uid=to_level.level_uid,
        to_x=tx,
        to_y=ty,
        system_passage_type="staircase",
        is_bidirectional=True,
    )
