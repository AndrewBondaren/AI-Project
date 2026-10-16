"""Pack offline completeness snapshot — WP-28."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.worldPack.packTilePlan import PackTileRef

PackCompleteness = Literal[
    "absent",
    "partial",
    "light_complete",
    "full_complete",
    "full_detailed_complete",
]


class PackCompletenessSnapshot(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-PACK-COMPLETENESS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    completeness: PackCompleteness = "absent"
    expected_l0_light: int = 0
    expected_l0_full: int = 0
    l0_baked: int = 0
    locations_expected: int = 0
    locations_detailed: int = 0
    # Cap used for light expected set: None = uncapped light priority; int = PackBakeDefaults / override
    light_cap: int | None = None
    missing_l0_full: list[PackTileRef] = Field(default_factory=list)
    missing_detailed: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness,
            "expected_l0_light": self.expected_l0_light,
            "expected_l0_full": self.expected_l0_full,
            "l0_baked": self.l0_baked,
            "locations_expected": self.locations_expected,
            "locations_detailed": self.locations_detailed,
            "light_cap": self.light_cap,
            "missing_l0_full": [
                {"gx": t.gx, "gy": t.gy} for t in self.missing_l0_full
            ],
            "missing_detailed": list(self.missing_detailed),
        }
