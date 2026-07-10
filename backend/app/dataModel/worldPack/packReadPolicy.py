"""Pack read-path defaults — MERGE-8 LRU decode."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class PackReadPolicy(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-PACK-READ-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    wilderness_chunk_lru_capacity: int = Field(default=64, ge=1)
    location_terrain_lru_capacity: int = Field(default=16, ge=1)

    @classmethod
    def canonical_defaults(cls) -> PackReadPolicy:
        return cls()
