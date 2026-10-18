"""Region state diagnostics routed through the project's loggingConfig facade."""

import logging
from collections.abc import Sequence

logger = logging.getLogger(__name__)


def log_overlap_rerank_deferred(world_uid: str, region_uid: str, neighbors: Sequence[str]) -> None:
    logger.warning(
        "region_state | overlap_rerank_deferred | world_uid=%s region_uid=%s neighbors=%s",
        world_uid, region_uid, ",".join(neighbors),
        extra={"activity": "overlap_rerank_deferred", "world_uid": world_uid,
               "region_uid": region_uid, "neighbors": list(neighbors)},
    )
