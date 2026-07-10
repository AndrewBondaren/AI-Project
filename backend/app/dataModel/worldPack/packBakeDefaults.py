"""Pack bake defaults — single source for debug orchestration caps."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class PackBakeDefaults(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-PACK-BAKE-DEFAULTS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    max_tiles_light: int = 16
    zstd_level: int = 3
    codec_version: int = 1
    background_drain_per_request: int = 0

    @classmethod
    def canonical_defaults(cls) -> PackBakeDefaults:
        return cls()
