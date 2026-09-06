"""Root POJO for `worlds.resource_type_registry` — extract N+1 resources."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import RootModel

from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.resources.resourceTypeEntry import ResourceTypeEntry

_CANONICAL_ENTRIES: tuple[ResourceTypeEntry, ...] = (
    ResourceTypeEntry(
        system_resource="iron_ore",
        resource_kind=ResourceKind.ORE,
        display_name="Железная руда",
        glossary_ref="res_iron_ore",
        is_renewable=False,
        default_yield=10,
        yield_item_uid="item_iron_ore",
        tag_refs=["tag_mineral"],
    ),
    ResourceTypeEntry(
        system_resource="copper_ore",
        resource_kind=ResourceKind.ORE,
        display_name="Медная руда",
        glossary_ref="res_copper_ore",
        is_renewable=False,
        default_yield=10,
        yield_item_uid="item_copper_ore",
        tag_refs=["tag_mineral"],
    ),
    ResourceTypeEntry(
        system_resource="timber",
        resource_kind=ResourceKind.TIMBER,
        display_name="Древесина",
        glossary_ref="res_timber",
        is_renewable=True,
        base_regen_per_tick=5,
        default_yield=5,
        yield_item_uid="item_log",
        tag_refs=["tag_natural"],
    ),
)


class WorldResourceTypeRegistry(RootModel[list[ResourceTypeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-RESOURCE"
    root: list[ResourceTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldResourceTypeRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_resource: str) -> ResourceTypeEntry | None:
        key = (system_resource or "").strip()
        for entry in self.root:
            if entry.system_resource == key:
                return entry
        return None

    def kind_for(self, system_resource: str) -> ResourceKind | None:
        entry = self.entry_for(system_resource)
        return None if entry is None else entry.resource_kind

    def keys(self) -> frozenset[str]:
        return frozenset(entry.system_resource for entry in self.root)

    def check_template_subjects(
        self,
        resource_kind: ResourceKind | None,
        subjects: Sequence[str],
    ) -> tuple[tuple[str, str], ...]:
        """Extract drawing: each subject must be this kind in the registry.

        Empty if ``resource_kind`` is omit (not an extract template).
        Codes: ``REF_W_UNKNOWN``, ``RESOURCE_KIND_MISMATCH``.
        """
        if resource_kind is None:
            return ()
        issues: list[tuple[str, str]] = []
        for raw in subjects:
            token = (raw or "").strip()
            if not token:
                continue
            entry = self.entry_for(token)
            if entry is None:
                issues.append((token, "REF_W_UNKNOWN"))
            elif entry.resource_kind != resource_kind:
                issues.append((token, "RESOURCE_KIND_MISMATCH"))
        return tuple(issues)
