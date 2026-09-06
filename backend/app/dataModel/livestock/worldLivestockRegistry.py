"""Root POJO for `worlds.livestock_registry` — livestock N+1 animals."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import RootModel

from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.livestock.livestockTypeEntry import LivestockTypeEntry

_CANONICAL_ENTRIES: tuple[LivestockTypeEntry, ...] = (
    LivestockTypeEntry(
        system_livestock="pig",
        livestock_kind=LivestockKind.MEAT,
        display_name="Свинья",
        glossary_ref="livestock_pig",
    ),
    LivestockTypeEntry(
        system_livestock="chicken",
        livestock_kind=LivestockKind.MEAT,
        display_name="Курица",
        glossary_ref="livestock_chicken",
    ),
    LivestockTypeEntry(
        system_livestock="cow",
        livestock_kind=LivestockKind.DAIRY,
        display_name="Корова",
        glossary_ref="livestock_cow",
    ),
    LivestockTypeEntry(
        system_livestock="sheep",
        livestock_kind=LivestockKind.FIBER,
        display_name="Овца",
        glossary_ref="livestock_sheep",
    ),
    LivestockTypeEntry(
        system_livestock="ox",
        livestock_kind=LivestockKind.DRAFT,
        display_name="Вол",
        glossary_ref="livestock_ox",
    ),
    LivestockTypeEntry(
        system_livestock="donkey",
        livestock_kind=LivestockKind.DRAFT,
        display_name="Осёл",
        glossary_ref="livestock_donkey",
    ),
    LivestockTypeEntry(
        system_livestock="horse",
        livestock_kind=LivestockKind.MOUNT,
        display_name="Лошадь",
        glossary_ref="livestock_horse",
    ),
)


class WorldLivestockRegistry(RootModel[list[LivestockTypeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-LIVESTOCK"
    root: list[LivestockTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldLivestockRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_livestock: str) -> LivestockTypeEntry | None:
        key = (system_livestock or "").strip()
        for entry in self.root:
            if entry.system_livestock == key:
                return entry
        return None

    def kind_for(self, system_livestock: str) -> LivestockKind | None:
        entry = self.entry_for(system_livestock)
        return None if entry is None else entry.livestock_kind

    def keys(self) -> frozenset[str]:
        return frozenset(entry.system_livestock for entry in self.root)

    def check_template_subjects(
        self,
        livestock_kind: LivestockKind | None,
        subjects: Sequence[str],
    ) -> tuple[tuple[str, str], ...]:
        """Livestock drawing: each subject must be this kind in the registry.

        Empty if ``livestock_kind`` is omit (generic / not a livestock template).
        Codes: ``REF_W_UNKNOWN``, ``LIVESTOCK_KIND_MISMATCH``.
        """
        if livestock_kind is None:
            return ()
        issues: list[tuple[str, str]] = []
        for raw in subjects:
            token = (raw or "").strip()
            if not token:
                continue
            entry = self.entry_for(token)
            if entry is None:
                issues.append((token, "REF_W_UNKNOWN"))
            elif entry.livestock_kind != livestock_kind:
                issues.append((token, "LIVESTOCK_KIND_MISMATCH"))
        return tuple(issues)
