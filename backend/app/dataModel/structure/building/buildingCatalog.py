"""Sync snapshot of generate-able building layouts for one settlement assembly.

CITY-T-2b. Not live SQL — caller hydrates, then passes this into assemblers.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.enums.buildingPurpose import (
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeMatch,
    coerce_purpose_match,
    purposes_match,
)


class BuildingCatalog:
    """``layouts`` unique by ``system_name`` (later wins). Ordered by ``system_name``."""

    def __init__(self, layouts: Iterable[BuildingLayoutTemplate]) -> None:
        by_name: dict[str, BuildingLayoutTemplate] = {}
        for layout in layouts:
            by_name[layout.system_name] = layout
        self._by_name = {name: by_name[name] for name in sorted(by_name)}
        self.layouts: tuple[BuildingLayoutTemplate, ...] = tuple(self._by_name.values())

    @classmethod
    def from_layouts(cls, layouts: Iterable[BuildingLayoutTemplate]) -> BuildingCatalog:
        return cls(layouts)

    @classmethod
    def empty(cls) -> BuildingCatalog:
        return cls(())

    def by_system_name(self, name: str) -> BuildingLayoutTemplate | None:
        return self._by_name.get(name)

    def of_structure_type(self, structure_type: str | BuildingPurpose) -> tuple[BuildingLayoutTemplate, ...]:
        purpose = (
            structure_type
            if isinstance(structure_type, BuildingPurpose)
            else BuildingPurpose.from_wire(structure_type)
        )
        if purpose is None:
            return ()
        return tuple(
            layout for layout in self.layouts if purpose in layout.structure_types
        )

    def matching_allowed(
        self,
        layouts: Iterable[BuildingLayoutTemplate],
        allowed: Iterable[AllowedToken] | None,
        mode: BuildingPurposeMatch | str | None,
    ) -> tuple[BuildingLayoutTemplate, ...]:
        """Filter drawings by district allowed + ``like`` / ``strict``."""
        pool = tuple(layouts)
        if allowed is None:
            return pool
        allowed_list = list(allowed)
        match = coerce_purpose_match(mode)
        return tuple(
            layout
            for layout in pool
            if purposes_match(layout.structure_types, allowed_list, match)
        )

    @staticmethod
    def prefer_subjects(
        layouts: tuple[BuildingLayoutTemplate, ...] | list[BuildingLayoutTemplate],
        subjects: tuple[str, ...] | list[str] | set[str],
        resource_kinds: tuple[ResourceKind, ...] | list[ResourceKind] | set[ResourceKind] | None = None,
        crop_kinds: tuple[CropKind, ...] | list[CropKind] | set[CropKind] | None = None,
        livestock_kinds: tuple[LivestockKind, ...] | list[LivestockKind] | set[LivestockKind] | None = None,
    ) -> tuple[BuildingLayoutTemplate, ...]:
        """Prefer instance-tagged drawings; else extract/farm/livestock kind; else untagged."""
        pool = tuple(layouts)
        wanted = {token.strip() for token in subjects if token and token.strip()}
        extract_kinds = {kind for kind in (resource_kinds or ()) if kind is not None}
        farm_kinds = {kind for kind in (crop_kinds or ()) if kind is not None}
        herd_kinds = {kind for kind in (livestock_kinds or ()) if kind is not None}
        if not wanted and not extract_kinds and not farm_kinds and not herd_kinds:
            return pool
        tagged = tuple(
            layout for layout in pool
            if wanted.intersection(layout.subjects or ())
        )
        if tagged:
            return tagged
        by_kind = tuple(
            layout for layout in pool
            if (
                layout.resource_kind is not None and layout.resource_kind in extract_kinds
            ) or (
                layout.crop_kind is not None and layout.crop_kind in farm_kinds
            ) or (
                layout.livestock_kind is not None and layout.livestock_kind in herd_kinds
            )
        )
        if by_kind:
            return by_kind
        untagged = tuple(
            layout for layout in pool
            if not layout.subjects
            and layout.resource_kind is None
            and layout.crop_kind is None
            and layout.livestock_kind is None
        )
        return untagged or pool

    def of_structure_type_for_subjects(
        self,
        structure_type: str,
        subjects: tuple[str, ...] | list[str] | set[str],
        resource_kinds: tuple[ResourceKind, ...] | list[ResourceKind] | set[ResourceKind] | None = None,
        crop_kinds: tuple[CropKind, ...] | list[CropKind] | set[CropKind] | None = None,
        livestock_kinds: tuple[LivestockKind, ...] | list[LivestockKind] | set[LivestockKind] | None = None,
    ) -> tuple[BuildingLayoutTemplate, ...]:
        return self.prefer_subjects(
            self.of_structure_type(structure_type),
            subjects, resource_kinds, crop_kinds, livestock_kinds,
        )

    def structure_types(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for layout in self.layouts:
            keys.update(str(purpose) for purpose in layout.structure_types)
        return tuple(sorted(keys))
