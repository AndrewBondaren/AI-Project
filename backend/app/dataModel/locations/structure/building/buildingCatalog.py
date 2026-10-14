"""Sync snapshot of generate-able plot members for one settlement assembly.

Not live SQL — caller hydrates the ``WorldTemplateSnapshot`` at the async
boundary, then passes this into assemblers. Identity is the library member
``template_uid`` (B3): bodies with equal local names from different packs
stay distinct. Purpose leaves of a plot come from its
``main_building.structure`` ref via ``StructureCatalog.leaves_of``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.enums.buildingPurpose import (
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeMatch,
    coerce_purpose_match,
    purposes_match,
)


@dataclass(frozen=True)
class CatalogPlot:
    """One catalog candidate: member identity + prepared plot body."""

    template_uid: str
    body: PlotLayoutTemplate


class BuildingCatalog:
    """``entries`` unique by ``template_uid`` (later wins). Ordered by uid."""

    def __init__(
        self,
        entries: Iterable[CatalogPlot],
        structures: StructureCatalog | None = None,
    ) -> None:
        by_uid: dict[str, CatalogPlot] = {}
        for entry in entries:
            by_uid[entry.template_uid] = entry
        self._by_uid = {uid: by_uid[uid] for uid in sorted(by_uid)}
        self.entries: tuple[CatalogPlot, ...] = tuple(self._by_uid.values())
        self.layouts: tuple[PlotLayoutTemplate, ...] = tuple(
            entry.body for entry in self.entries
        )
        self.structures = structures if structures is not None else StructureCatalog.empty()

    @classmethod
    def from_entries(
        cls,
        entries: Mapping[str, PlotLayoutTemplate] | Iterable[tuple[str, PlotLayoutTemplate]],
        structures: StructureCatalog | None = None,
    ) -> BuildingCatalog:
        """From caller-declared ``(template_uid, body)`` pairs."""
        pairs = entries.items() if isinstance(entries, Mapping) else entries
        return cls(
            (CatalogPlot(uid, body) for uid, body in pairs),
            structures,
        )

    @classmethod
    def from_layouts(
        cls,
        layouts: Iterable[PlotLayoutTemplate],
        structures: StructureCatalog | None = None,
    ) -> BuildingCatalog:
        """Synthetic entries keyed by body ``system_name`` — test/debug seam
        for layouts that are not library members. Runtime packing reads
        member identities from the world snapshot instead."""
        return cls.from_entries(
            ((str(layout.system_name), layout) for layout in layouts),
            structures,
        )

    @classmethod
    def empty(cls) -> BuildingCatalog:
        return cls(())

    def by_uid(self, template_uid: str) -> PlotLayoutTemplate | None:
        entry = self._by_uid.get(str(template_uid))
        return entry.body if entry is not None else None

    def entry_for(self, template_uid: str) -> CatalogPlot | None:
        return self._by_uid.get(str(template_uid))

    def of_structure_type(self, structure_type: str | BuildingPurpose) -> tuple[CatalogPlot, ...]:
        purpose = (
            structure_type
            if isinstance(structure_type, BuildingPurpose)
            else BuildingPurpose.from_wire(structure_type)
        )
        if purpose is None:
            return ()
        return tuple(
            entry for entry in self.entries
            if purpose in self.structures.leaves_of(entry.body)
        )

    def matching_allowed(
        self,
        entries: Iterable[CatalogPlot],
        allowed: Iterable[AllowedToken] | None,
        mode: BuildingPurposeMatch | str | None,
    ) -> tuple[CatalogPlot, ...]:
        """Filter drawings by district allowed + ``like`` / ``strict``."""
        pool = tuple(entries)
        if allowed is None:
            return pool
        allowed_list = list(allowed)
        match = coerce_purpose_match(mode)
        return tuple(
            entry
            for entry in pool
            if purposes_match(self.structures.leaves_of(entry.body), allowed_list, match)
        )

    @staticmethod
    def prefer_subjects(
        entries: tuple[CatalogPlot, ...] | list[CatalogPlot],
        subjects: tuple[str, ...] | list[str] | set[str],
        resource_kinds: tuple[ResourceKind, ...] | list[ResourceKind] | set[ResourceKind] | None = None,
        crop_kinds: tuple[CropKind, ...] | list[CropKind] | set[CropKind] | None = None,
        livestock_kinds: tuple[LivestockKind, ...] | list[LivestockKind] | set[LivestockKind] | None = None,
    ) -> tuple[CatalogPlot, ...]:
        """Prefer instance-tagged drawings; else extract/farm/livestock kind; else untagged."""
        pool = tuple(entries)
        wanted = {token.strip() for token in subjects if token and token.strip()}
        extract_kinds = {kind for kind in (resource_kinds or ()) if kind is not None}
        farm_kinds = {kind for kind in (crop_kinds or ()) if kind is not None}
        herd_kinds = {kind for kind in (livestock_kinds or ()) if kind is not None}
        if not wanted and not extract_kinds and not farm_kinds and not herd_kinds:
            return pool

        def tagged_with(entry: CatalogPlot) -> bool:
            return bool(wanted.intersection(entry.body.subjects or ()))

        tagged = tuple(entry for entry in pool if tagged_with(entry))
        if tagged:
            return tagged
        by_kind = tuple(
            entry for entry in pool
            if (
                entry.body.resource_kind is not None and entry.body.resource_kind in extract_kinds
            ) or (
                entry.body.crop_kind is not None and entry.body.crop_kind in farm_kinds
            ) or (
                entry.body.livestock_kind is not None and entry.body.livestock_kind in herd_kinds
            )
        )
        if by_kind:
            return by_kind
        untagged = tuple(
            entry for entry in pool
            if not entry.body.subjects
            and entry.body.resource_kind is None
            and entry.body.crop_kind is None
            and entry.body.livestock_kind is None
        )
        return untagged or pool

    def of_structure_type_for_subjects(
        self,
        structure_type: str,
        subjects: tuple[str, ...] | list[str] | set[str],
        resource_kinds: tuple[ResourceKind, ...] | list[ResourceKind] | set[ResourceKind] | None = None,
        crop_kinds: tuple[CropKind, ...] | list[CropKind] | set[CropKind] | None = None,
        livestock_kinds: tuple[LivestockKind, ...] | list[LivestockKind] | set[LivestockKind] | None = None,
    ) -> tuple[CatalogPlot, ...]:
        return self.prefer_subjects(
            self.of_structure_type(structure_type),
            subjects, resource_kinds, crop_kinds, livestock_kinds,
        )

    def structure_types(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for entry in self.entries:
            keys.update(str(purpose) for purpose in self.structures.leaves_of(entry.body))
        return tuple(sorted(keys))
