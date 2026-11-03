"""Spatial read failure vocabulary from the Spatial read contract."""
from enum import StrEnum


class SpatialReadFailureReason(StrEnum):
    FRAME_MISMATCH = "frame_mismatch"
    REVISION_MISMATCH = "revision_mismatch"
    SOURCE_MISSING = "source_missing"
    SOURCE_CORRUPT = "source_corrupt"
    UNSUPPORTED_FORMAT = "unsupported_format"
    SOURCE_INCOMPLETE = "source_incomplete"
    DOMAIN_REJECTED = "domain_rejected"
    RESOURCE_LIMIT = "resource_limit"
    SOURCE_UNAVAILABLE = "source_unavailable"
