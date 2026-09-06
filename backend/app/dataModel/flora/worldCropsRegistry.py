"""Root POJO for `worlds.crops_registry` — farm N+1 crops."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import RootModel

from app.dataModel.flora.cropsTypeEntry import CropsTypeEntry
from app.dataModel.flora.enums.cropKind import CropKind

_CANONICAL_ENTRIES: tuple[CropsTypeEntry, ...] = (
    CropsTypeEntry(
        system_crop="wheat",
        crop_kind=CropKind.GRAIN,
        display_name="Пшеница",
        glossary_ref="crop_wheat",
    ),
    CropsTypeEntry(
        system_crop="cabbage",
        crop_kind=CropKind.VEGETABLE,
        display_name="Капуста",
        glossary_ref="crop_cabbage",
    ),
    CropsTypeEntry(
        system_crop="apple",
        crop_kind=CropKind.FRUIT,
        display_name="Яблоко",
        glossary_ref="crop_apple",
    ),
    CropsTypeEntry(
        system_crop="flax",
        crop_kind=CropKind.FIBER,
        display_name="Лён",
        glossary_ref="crop_flax",
    ),
    CropsTypeEntry(
        system_crop="hay",
        crop_kind=CropKind.FODDER,
        display_name="Сено",
        glossary_ref="crop_hay",
    ),
)


class WorldCropsRegistry(RootModel[list[CropsTypeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CROPS"
    root: list[CropsTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldCropsRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_crop: str) -> CropsTypeEntry | None:
        key = (system_crop or "").strip()
        for entry in self.root:
            if entry.system_crop == key:
                return entry
        return None

    def kind_for(self, system_crop: str) -> CropKind | None:
        entry = self.entry_for(system_crop)
        return None if entry is None else entry.crop_kind

    def keys(self) -> frozenset[str]:
        return frozenset(entry.system_crop for entry in self.root)

    def check_template_subjects(
        self,
        crop_kind: CropKind | None,
        subjects: Sequence[str],
    ) -> tuple[tuple[str, str], ...]:
        """Farm drawing: each subject must be this kind in the registry.

        Empty if ``crop_kind`` is omit (not a farm template).
        Codes: ``REF_W_UNKNOWN``, ``CROP_KIND_MISMATCH``.
        """
        if crop_kind is None:
            return ()
        issues: list[tuple[str, str]] = []
        for raw in subjects:
            token = (raw or "").strip()
            if not token:
                continue
            entry = self.entry_for(token)
            if entry is None:
                issues.append((token, "REF_W_UNKNOWN"))
            elif entry.crop_kind != crop_kind:
                issues.append((token, "CROP_KIND_MISMATCH"))
        return tuple(issues)
