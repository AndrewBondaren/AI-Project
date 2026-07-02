"""
Staircase builder — оркестратор.

Читает staircase_type из room definition, диспатчит к нужному builder-классу,
создаёт и возвращает LocationPassage.
"""
import logging
import uuid

from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.straight  import StraightBuilder
from app.application.worldData.generators.structure.staircase.uShape    import UShapeBuilder
from app.application.worldData.generators.structure.staircase.spiral    import SpiralBuilder
from app.application.worldData.generators.structure.staircase.verticalLadder  import VerticalLadderBuilder, ExternalVerticalLadderBuilder
from app.application.worldData.generators.structure.staircase.base      import StaircaseBuilder
from app.application.worldData.generators.structure.staircase.staircaseType import StaircaseType
from app.dataModel.structure.enums.passageType import PassageType
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_BUILDERS: dict[StaircaseType, type[StaircaseBuilder]] = {
    StaircaseType.STRAIGHT:                 StraightBuilder,
    StaircaseType.U_SHAPE:                  UShapeBuilder,
    StaircaseType.SPIRAL:                   SpiralBuilder,
    StaircaseType.VERTICAL_LADDER:          VerticalLadderBuilder,
    StaircaseType.EXTERNAL_VERTICAL_LADDER: ExternalVerticalLadderBuilder,
}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def build_staircase(
    conn_or_entry: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    mat: str,
    *,
    shaft: "_RoomInstance | None" = None,
    passage_height: int,
) -> "tuple[LocationPassage | None, StaircaseBuilder | None]":
    is_new_schema = shaft is not None or "staircase_id" in conn_or_entry
    if is_new_schema:
        # New schema: staircase_type and id come from sc_entry (staircases[] array)
        stair_type_raw = conn_or_entry.get("staircase_type", "u_shape")
        sc_id      = conn_or_entry.get("staircase_id", "?")
        conn_label = f"{sc_id}  {fr.room_id}->{to.room_id}"
    else:
        # Old schema: type inferred from to.staircase_type + underground check
        conn_label        = f"{conn_or_entry['from_room']}->{conn_or_entry['to_room']}"
        going_underground = (fr.z_offset >= 0 and to.z_offset < 0)
        coming_up         = (fr.z_offset <  0 and to.z_offset >= 0)
        stair_type_raw = "trapdoor" if (going_underground or coming_up) else getattr(to, "staircase_type", None)

    stair_type = StaircaseType.from_wire(stair_type_raw or "")
    logger.info("build_staircase: %s  stair_type=%r  z_height=%d",
                conn_label, stair_type_raw, abs(to_level.z - fr_level.z))

    if stair_type is None or stair_type not in _BUILDERS:
        logger.error("staircase %s: unknown staircase_type=%r", conn_label, stair_type_raw)
        return None, None

    builder = _BUILDERS[stair_type](
        fr, to, fr_level, to_level, cells, world_uid, building_uid, mat, conn_label,
        shaft=shaft,
        sc_entry=conn_or_entry,
        passage_height=passage_height,
    )

    try:
        fr_anchor, to_anchor = builder.build()
        builder.clear_shaft()
        builder.lay_base_floor()
    except NotImplementedError:
        logger.error("staircase %s: %s not implemented", conn_label, stair_type)
        return None, None

    fx, fy = fr_anchor
    tx, ty = to_anchor
    if is_new_schema:
        passage_uid = _det_uuid(building_uid, "stair", conn_or_entry.get("staircase_id", "?"),
                                fr.room_id, to.room_id)
    else:
        passage_uid = _det_uuid(building_uid, "stair",
                                conn_or_entry["from_room"], conn_or_entry["to_room"])
    passage = LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=fx,
        from_y=fy,
        to_level_uid=to_level.level_uid,
        to_x=tx,
        to_y=ty,
        system_passage_type=PassageType.STAIRCASE,
        is_bidirectional=True,
    )
    return passage, builder
