"""Nullable world-side pack reference; filesystem checks belong to orchestration."""

from typing import Any, ClassVar
from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.worldScalarWire import pojo_wire_keys, scalar_wire_from_mapping, validate_world_row_pojo_columns


class WorldPackMetadata(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PACK-METADATA"
    model_config = ConfigDict(extra="ignore", frozen=True)

    terrain_pack_path: DefaultWhenMissing[str | None] = None
    terrain_pack_hash: DefaultWhenMissing[str | None] = None

    @classmethod
    def canonical_defaults(cls) -> "WorldPackMetadata":
        return cls()


PACK_METADATA_WIRE_KEYS = pojo_wire_keys(WorldPackMetadata)


def pack_metadata_wire_from_mapping(source: Any) -> dict[str, Any]:
    return scalar_wire_from_mapping(PACK_METADATA_WIRE_KEYS, source)


def validate_world_row_pack_metadata_columns(world_cls: type) -> None:
    validate_world_row_pojo_columns(world_cls, WorldPackMetadata, label="pack metadata")
