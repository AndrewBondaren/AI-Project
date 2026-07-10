"""chunk_refine_jobs row — WP-12 recovery."""

from dataclasses import dataclass


@dataclass
class ChunkRefineJob:
    __table__ = "chunk_refine_jobs"
    __pk__    = "job_uid"

    job_uid:        str
    world_uid:      str
    gx:             int
    gy:             int
    cx:             int
    cy:             int
    status:         str = "pending"
    priority:       float = 0.0
    content_hash:   str | None = None
    created_at:     str
    updated_at:     str
