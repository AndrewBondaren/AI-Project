"""Fine terrain chunk column-run wire inside zstd blobs."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class FineTerrainZRun(BaseModel):
    """Contiguous z band with constant terrain/material registry keys."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    z0: int
    z1: int
    system_terrain: str
    system_material: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_wire(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if data.get("system_terrain"):
            return data
        terrain_id = data.get("terrain_id")
        material_id = data.get("material_id")
        migrated = dict(data)
        if terrain_id is not None and "system_terrain" not in migrated:
            migrated["system_terrain"] = f"terrain_{int(terrain_id)}"
            migrated.pop("terrain_id", None)
        if material_id and int(material_id) != 0:
            migrated["system_material"] = f"material_{int(material_id)}"
            migrated.pop("material_id", None)
        return migrated

    def cells(self) -> list[tuple[int, int, int]]:
        z_lo, z_hi = min(self.z0, self.z1), max(self.z0, self.z1)
        return [(0, 0, z) for z in range(z_lo, z_hi + 1)]


class FineTerrainColumnWire(BaseModel):
    """One fine column (lx, ly) with z-runs."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    lx: int
    ly: int
    runs: list[FineTerrainZRun]


class FineTerrainChunkWire(BaseModel):
    """Fine chunk payload — default 32×32 m columns."""

    SCHEMA_ID: ClassVar[str] = "SCH-FINE-TERRAIN-CHUNK-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    cx: int
    cy: int
    chunk_columns: int
    columns: list[FineTerrainColumnWire]

    @field_validator("chunk_columns")
    @classmethod
    def _positive_chunk(cls, value: int) -> int:
        if value < 1:
            raise ValueError("chunk_columns must be >= 1")
        return value
