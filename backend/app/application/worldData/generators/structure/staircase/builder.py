from app.dataModel.locations.transitions.transitionParams import StaircaseTransitionParams
"""
Staircase builder — оркестратор.

Читает staircase_type из room definition, диспатчит к нужному builder-классу,
создаёт и возвращает Transition.
"""
import logging

from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.straight  import StraightBuilder
from app.application.worldData.generators.structure.staircase.uShape    import UShapeBuilder
from app.application.worldData.generators.structure.staircase.spiral    import SpiralBuilder
from app.application.worldData.generators.structure.staircase.verticalLadder  import VerticalLadderBuilder, ExternalVerticalLadderBuilder
from app.application.worldData.generators.structure.staircase.base      import StaircaseBuilder
from app.dataModel.locations.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.locations.structure.enums.staircaseType import StaircaseType
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.db.models.locationLevel import LocationLevel
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.application.worldData.generators.structure.physicalTransition import physical_transition, level_endpoint
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_BUILDERS: dict[StaircaseType, type[StaircaseBuilder]] = {
    StaircaseType.STRAIGHT:                 StraightBuilder,
    StaircaseType.U_SHAPE:                  UShapeBuilder,
    StaircaseType.SPIRAL:                   SpiralBuilder,
    StaircaseType.VERTICAL_LADDER:          VerticalLadderBuilder,
    StaircaseType.EXTERNAL_VERTICAL_LADDER: ExternalVerticalLadderBuilder,
}


def build_staircase(
    sc: StaircaseSpec,
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
) -> "tuple[Transition | None, StaircaseBuilder | None]":
    sc_id      = sc.staircase_id
    conn_label = f"{sc_id}  {fr.room_id}->{to.room_id}"
    stair_type = sc.staircase_type
    logger.info("build_staircase: %s  stair_type=%r  z_height=%d",
                conn_label, stair_type, abs(to_level.z - fr_level.z))

    if stair_type not in _BUILDERS:
        logger.error("staircase %s: unknown staircase_type=%r", conn_label, stair_type)
        return None, None

    builder = _BUILDERS[stair_type](
        fr, to, fr_level, to_level, cells, world_uid, building_uid, mat, conn_label,
        shaft=shaft,
        sc_entry=sc,
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
    passage = physical_transition(world_uid, TransitionType.STAIRCASE, level_endpoint(fr_level, fx, fy, building_uid), level_endpoint(to_level, tx, ty, building_uid), building_uid, type_params=StaircaseTransitionParams(staircase_type=stair_type))
    return passage, builder
