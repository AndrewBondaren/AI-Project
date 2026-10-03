"""Root POJO for ``worlds.purpose_packs`` — enabled mask ids. tz_building_generator.md §2.1."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import RootModel, field_validator

from app.dataModel.structure.enums.buildingPurpose.packs import (
    PurposePack,
    coerce_purpose_packs,
)


class WorldPurposePacks(RootModel[list[str]]):
    """Enabled pack ids (N+1). Builtin names are ``PurposePack`` values."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PURPOSE-PACKS"
    root: list[str]

    @classmethod
    def canonical_defaults(cls) -> WorldPurposePacks:
        return cls([PurposePack.BASE, PurposePack.FANTASY])

    @field_validator("root", mode="before")
    @classmethod
    def _coerce_root(cls, value: Any) -> list[str]:
        return coerce_purpose_packs(value)
