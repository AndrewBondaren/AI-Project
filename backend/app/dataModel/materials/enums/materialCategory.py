"""Wire ``material_category`` — ENUM-E (solid / liquid / gas). tz_materials.md §2."""

from __future__ import annotations

from enum import StrEnum


class MaterialCategory(StrEnum):
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"

    def is_liquid(self) -> bool:
        return self is MaterialCategory.LIQUID
