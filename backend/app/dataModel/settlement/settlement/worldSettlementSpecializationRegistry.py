"""Root POJO for `worlds.settlement_specialization_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.settlement.settlement.settlementSpecializationEntry import (
    SettlementSpecializationEntry,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef

_CANONICAL_ENTRIES: tuple[SettlementSpecializationEntry, ...] = (
    SettlementSpecializationEntry(
        system_specialization="extract",
        display_specialization="Добыча",
        subject_kind="resource",
        typical_districts=[
            TypicalDistrictRef(district_type="industrial", district_subtype="extract"),
        ],
        required_structure_types=["mine"],
    ),
    SettlementSpecializationEntry(
        system_specialization="process",
        display_specialization="Обработка",
        subject_kind="product",
        typical_districts=[
            TypicalDistrictRef(district_type="industrial", district_subtype="process"),
        ],
        required_structure_types=["mill", "smelter"],
    ),
    SettlementSpecializationEntry(
        system_specialization="manufacture",
        display_specialization="Производство",
        subject_kind="product",
        typical_districts=[
            TypicalDistrictRef(
                district_type="industrial", district_subtype="manufacture",
            ),
        ],
        required_structure_types=["workshop"],
    ),
    SettlementSpecializationEntry(
        system_specialization="culture",
        display_specialization="Культура",
        subject_kind="domain",
        typical_districts=[
            TypicalDistrictRef(district_type="civic", district_subtype="culture"),
        ],
        required_structure_types=["temple", "theater"],
        subjects_to_structure_types={
            "religion": ["temple"],
            "knowledge": ["library"],
        },
    ),
    SettlementSpecializationEntry(
        system_specialization="farm",
        display_specialization="Выращивание",
        subject_kind="crop",
        typical_districts=[
            TypicalDistrictRef(district_type="agricultural", district_subtype="farm"),
        ],
        required_structure_types=["farm"],
    ),
    SettlementSpecializationEntry(
        system_specialization="livestock",
        display_specialization="Скотоводство",
        subject_kind="livestock",
        typical_districts=[
            TypicalDistrictRef(
                district_type="agricultural", district_subtype="livestock",
            ),
        ],
        required_structure_types=["livestock"],
    ),
)


class WorldSettlementSpecializationRegistry(RootModel[list[SettlementSpecializationEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-SETTLEMENT-SPEC"
    RUNTIME_MERGE_ID_FIELD: ClassVar[str] = "system_specialization"
    root: list[SettlementSpecializationEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldSettlementSpecializationRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_specialization: str) -> SettlementSpecializationEntry | None:
        key = (system_specialization or "").strip()
        for entry in self.root:
            if entry.system_specialization == key:
                return entry
        return None
