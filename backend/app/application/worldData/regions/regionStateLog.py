"""Region state diagnostics routed through the project's loggingConfig facade."""

import logging
from collections.abc import Sequence
from app.dataModel.regions.regionState import RegionState, RegionStateTransition

logger = logging.getLogger(__name__)


def log_evaluation(world_uid: str, state: RegionState, parent_region_uid: str | None) -> None:
    logger.debug(
        "region_state | evaluation | world_uid=%s region_uid=%s parent_region_uid=%s "
        "current_type=%s pending_target=%s progress=%s last_eval_tick=%s",
        world_uid, state.region_uid, parent_region_uid, state.current_type,
        state.pending_target, state.progress, state.last_eval_tick,
        extra={"activity": "evaluation", "world_uid": world_uid,
               "region_uid": state.region_uid, "parent_region_uid": parent_region_uid,
               "current_type": state.current_type, "pending_target": state.pending_target,
               "progress": state.progress, "last_eval_tick": state.last_eval_tick},
    )


def log_transition(world_uid: str, region_uid: str, transition: RegionStateTransition) -> None:
    logger.info(
        "region_state | transition | world_uid=%s region_uid=%s from_type=%s to_type=%s cause=%s at=%s",
        world_uid, region_uid, transition.from_type, transition.to_type, transition.cause, transition.at,
        extra={"activity": "transition", "world_uid": world_uid, "region_uid": region_uid,
               **transition.model_dump(mode="json")},
    )


def log_overlap_rerank_deferred(world_uid: str, region_uid: str, neighbors: Sequence[str]) -> None:
    logger.warning(
        "region_state | overlap_rerank_deferred | world_uid=%s region_uid=%s neighbors=%s",
        world_uid, region_uid, ",".join(neighbors),
        extra={"activity": "overlap_rerank_deferred", "world_uid": world_uid,
               "region_uid": region_uid, "neighbors": list(neighbors)},
    )
