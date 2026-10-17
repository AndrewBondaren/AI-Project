"""Reject ambiguous entity identities before any paint or index publication."""
import logging
from collections.abc import Iterable
from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion

logger = logging.getLogger(__name__)


def require_unique_region_uids(regions: Iterable[ResolvedRegion]) -> None:
    seen: set[str] = set()
    for region in regions:
        for uid in (region.region_uid, *(s.region_uid for s in region.sublocations)):
            if uid in seen:
                logger.error("landcover | region_uid_conflict | region_uid=%s", uid)
                raise ValueError(f"duplicate wilderness entity UID: {uid}")
            seen.add(uid)
