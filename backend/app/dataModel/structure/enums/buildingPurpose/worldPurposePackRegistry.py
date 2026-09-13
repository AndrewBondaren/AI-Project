"""Root POJO for ``worlds.purpose_pack_registry`` — pack recipes, not the purpose tree."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import ClassVar

from pydantic import RootModel

from app.dataModel.registryKey import RegistryKey
from app.dataModel.structure.enums.buildingPurpose.catalog import (
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeFamily,
    expand_allowed,
)
import app.dataModel.structure.enums.buildingPurpose.purposePackEntry as _entry_mod
from app.dataModel.structure.enums.buildingPurpose.packs import (
    PurposePack,
    coerce_purpose_packs,
)
from app.dataModel.structure.enums.buildingPurpose.purposePackEntry import PurposePackEntry

logger = logging.getLogger(__name__)


class WorldPurposePackRegistry(RootModel[list[PurposePackEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PURPOSE-PACK-REGISTRY"
    RUNTIME_MERGE_ID_FIELD: ClassVar[str] = "system_pack"
    root: list[PurposePackEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldPurposePackRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_pack: str) -> PurposePackEntry | None:
        key = (system_pack or "").strip().lower()
        for entry in self.root:
            if str(entry.system_pack) == key:
                return entry
        return None

    def with_frozen_base(self) -> WorldPurposePackRegistry:
        """World overlay cannot replace the ``base`` fabric recipe."""
        canon = type(self).canonical_defaults().entry_for(PurposePack.BASE)
        if canon is None:
            raise RuntimeError("canonical purpose pack registry missing base")
        rest = [
            entry for entry in self.root
            if str(entry.system_pack) != PurposePack.BASE
        ]
        return type(self)([canon, *rest])


type PurposePackKey = RegistryKey[WorldPurposePackRegistry]

_entry_mod.WorldPurposePackRegistry = WorldPurposePackRegistry
PurposePackEntry.model_rebuild()


def _recipe(pack: PurposePack, *allowed: AllowedToken) -> PurposePackEntry:
    return PurposePackEntry(system_pack=pack, allowed=list(allowed))


_MODERN_ALLOWED: tuple[AllowedToken, ...] = (
    BuildingPurpose.CHURCH,
    BuildingPurpose.HOSPITAL,
    BuildingPurpose.SCHOOL,
    BuildingPurpose.CAFE,
    BuildingPurpose.RESTAURANT,
    BuildingPurpose.HYPERMARKET,
    BuildingPurposeFamily.DIPLOMATIC,
    BuildingPurposeFamily.UTILITY,
    BuildingPurpose.ACADEMY,
    BuildingPurpose.LABORATORY,
    BuildingPurpose.LEGISLATURE,
)

_CANONICAL_ENTRIES: tuple[PurposePackEntry, ...] = (
    _recipe(
        PurposePack.BASE,
        BuildingPurposeFamily.DWELLING,
        BuildingPurpose.TOWN_HALL,
        BuildingPurpose.PLAZA,
        BuildingPurpose.BATHHOUSE,
        BuildingPurpose.COURTHOUSE,
        BuildingPurpose.THEATER,
        BuildingPurpose.LIBRARY,
        BuildingPurpose.CHANCERY,
        BuildingPurpose.SHOP,
        BuildingPurpose.MARKET,
        BuildingPurpose.BAKERY,
        BuildingPurpose.BUTCHER,
        BuildingPurpose.FISHMONGER,
        BuildingPurpose.GREENGROCER,
        BuildingPurpose.APOTHECARY,
        BuildingPurpose.TAILOR,
        BuildingPurpose.COBBLER,
        BuildingPurpose.JEWELER,
        BuildingPurpose.BOOKSELLER,
        BuildingPurposeFamily.LOGISTICS,
        BuildingPurposeFamily.CRAFT,
        BuildingPurposeFamily.EXTRACT,
        BuildingPurposeFamily.PROCESS,
        BuildingPurposeFamily.CULTIVATION,
        BuildingPurposeFamily.HUSBANDRY,
        BuildingPurposeFamily.DEFENSE,
        BuildingPurposeFamily.HARBOR,
    ),
    _recipe(
        PurposePack.FANTASY,
        BuildingPurpose.TEMPLE,
        BuildingPurpose.SHRINE,
        BuildingPurpose.TAVERN,
        BuildingPurpose.GUILD,
        BuildingPurpose.PALACE,
        BuildingPurpose.ACADEMY,
    ),
    _recipe(
        PurposePack.MAGIC,
        BuildingPurpose.PORTAL,
        BuildingPurpose.TEMPLE,
        BuildingPurpose.SHRINE,
        BuildingPurpose.ARCANE_LAB,
        BuildingPurpose.ACADEMY,
    ),
    _recipe(
        PurposePack.STEAMPUNK,
        BuildingPurposeFamily.FACTORY,
        BuildingPurposeFamily.UTILITY,
        BuildingPurpose.LABORATORY,
    ),
    _recipe(PurposePack.MODERN, *_MODERN_ALLOWED),
    _recipe(
        PurposePack.SCI_FI,
        *_MODERN_ALLOWED,
        BuildingPurposeFamily.FACTORY,
        BuildingPurpose.PORTAL,
        BuildingPurpose.AIR_DOCK,
    ),
)

_CANONICAL_IDS = {str(entry.system_pack) for entry in _CANONICAL_ENTRIES}
if _CANONICAL_IDS != {member.value for member in PurposePack}:
    raise RuntimeError(
        "WorldPurposePackRegistry canonical recipes must list every PurposePack: "
        f"{sorted(_CANONICAL_IDS ^ {member.value for member in PurposePack})}"
    )


def purposes_for_world(
    packs: Iterable[object] | None = None,
    recipes: WorldPurposePackRegistry | None = None,
) -> frozenset[BuildingPurpose]:
    """Omit / empty → ``[base, fantasy]``. Mix = union. ``base`` always included."""
    registry = recipes or WorldPurposePackRegistry.canonical_defaults()
    enabled: set[BuildingPurpose] = set()
    for pack_id in coerce_purpose_packs(packs):
        entry = registry.entry_for(pack_id)
        if entry is None:
            logger.warning(
                "Unknown purpose pack %r — dropped (not inventing leaves)",
                pack_id,
            )
            continue
        enabled.update(expand_allowed(entry.allowed))
    return frozenset(enabled)
