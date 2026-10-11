"""Domain adapter contract of the pack application service — plan steps
4a–4c, TZ §0.2/§2.

The universal pack layer (``packService``) owns identity, ownership and
atomicity; each adapter owns the body model, domain restrictions and the
transitional pointer dual-write: registry pointers stay the availability
source of truth until step 5b, so a world-owned member write must appear
to the existing registry readers (``load_relief_templates_for_world``,
``layouts_for_world``) through the pointer row — always pointing at the
world-owned member uid, never at an engine member.

This package holds the contract only (``contract.py``): the
``PackDomainAdapter`` ABC, the domain library/outline unions, the shared
wire-key constants and ``RemappedMember``. Shared mixins live in
``mixins``, world/body ref scanners in ``remapRefs``, concrete adapters
in ``{relief,structure,building}``, the container seam in ``factory``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.dataModel.locations.structure.building.buildingTemplateOutline import (
    BuildingTemplateOutline,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.lifecycleContracts import FallbackDecision, MemberRef

if TYPE_CHECKING:
    from app.application.worldData.reliefTemplateFsImport import ReliefPackImport
    from app.application.worldData.structureTemplateFsImport import StructurePackImport

DomainLibrary = (
    ReliefTemplateLibraryService
    | StructureTemplateLibraryService
    | BuildingTemplateLibraryService
)

DomainOutline = (
    ReliefTemplate
    | StructureTemplate
    | BuildingTemplateOutline
    | PlotLayoutTemplate
)

_POINTER_UID_FIELD = "system_template_uid"
"""Shared uid-pointer field of ``ReliefTemplateRegistryEntry`` /
``BuildingTemplateRegistryEntry`` rows. Heterogeneous columns are
scanned on this key because embedded plot layouts carry no pointer."""

_SYSTEM_NAME_FIELD = "system_name"
"""``StructureTemplate.system_name`` wire key — the model-A member uid."""


@dataclass(frozen=True)
class RemappedMember:
    """Instance member + its parsed outline — ``remap_world_refs`` input."""
    member: LibraryPackMemberRow
    outline: DomainOutline


class PackDomainAdapter(ABC):
    """Body/pointer contract of one ``library_kind`` for the pack service.

    All methods run inside the caller's transaction — an adapter never owns
    atomicity. Declared body/world references feed the common usage index;
    the lifecycle job decides retention and deletion.
    """

    library_kind: ClassVar[LibraryKind]

    @abstractmethod
    def prepare_body(self, raw: dict, *, local_uid: str, template_uid: str,
                     world: World | None = None) -> DomainOutline:
        """Pure validation/normalization shared by preview and persistence."""

    def body_refs(self, body: dict, consumer: str) -> tuple[MemberRef, ...]:
        return ()

    def world_refs(self, world: World) -> tuple[MemberRef, ...]:
        return ()

    @abstractmethod
    async def write_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        pack: LibraryPackRow,
        world: World | None,
        source_file: str | None = None,
    ) -> Any:
        """Validate + persist the body; return the parsed outline.

        Raise ``LibraryPackValidationError`` on invalid body or when the
        body's own identity does not agree with the member identity.
        ``world`` is the owning world for world-owned packs (domain
        restrictions resolve against its registries), else None.
        """

    @abstractmethod
    async def read_body_row(
        self, template_uid: str
    ) -> tuple[dict, str | None] | None:
        """Body wire dict + diagnostic ``source_file`` in one read, or
        None when absent — the single library read of the remap path."""

    async def read_body(self, template_uid: str) -> dict | None:
        """Wire dict of the body row, or None when absent."""
        found = await self.read_body_row(template_uid)
        return None if found is None else found[0]

    async def body_source_file(self, template_uid: str) -> str | None:
        """Diagnostic ``source_file`` of the body row — carried into copies."""
        found = await self.read_body_row(template_uid)
        return None if found is None else found[1]

    @abstractmethod
    async def delete_body(self, template_uid: str) -> None:
        """Remove the body row; tolerate an already-missing row."""

    async def import_fs_pack(
        self, path: str | Path, *, domain_root: Path | None = None
    ) -> ReliefPackImport | StructurePackImport:
        """Manifest-based FS import → ``(manifest, body rows)`` outcome.

        Domain bodies land via the library service; catalog attach is the
        service's job (same unit of work).
        """
        raise LibraryPackValidationError(
            f"library_kind '{self.library_kind.value}' has no FS domain root"
        )

    async def ensure_pointer(
        self, world: World, member: LibraryPackMemberRow, outline: Any
    ) -> None:
        """Dual-write: refresh the world registry pointer for a member."""

    async def drop_pointer(self, world: World, template_uid: str) -> None:
        """Dual-write: remove the world registry pointer for a member."""

    # ------------------------------------------------------------------
    # Runtime resolve contract (TZ §5) — effective catalog, step 5a-2.
    # ------------------------------------------------------------------

    def resolve_fallback(self, *, world_uid: str) -> FallbackDecision:
        """Domain decision for a ref that did not resolve to an available body
        (unknown uid, owner unavailable, missing dependency, missing body,
        empty ref, explicit default marker).

        Domains with a POJO default layer answer ``FallbackDecision.default``;
        domains without a substitution contract keep the base ``rejected``
        (relief R21: no other template is ever substituted). Pure — the
        resolve boundary emits the single warning record.
        """
        return FallbackDecision.rejected()

    # ------------------------------------------------------------------
    # Remap contract (TZ §2) — instantiate_pack / copy_pack, step 4b.
    # ------------------------------------------------------------------

    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str], local_uid: str | None = None,
    ) -> dict:
        """Copied member body for the new owner.

        Rewrites the embedded member uid (model A bodies) and refs to
        source-pack members by ``uid_map``; refs absent from the map —
        other packs, external bodies — stay untouched.
        """
        return dict(body)

    def prepare_world_refs(self, world: World, uid_map: Mapping[str, str],
                           members: Sequence[RemappedMember], *, removed_uids: Sequence[str] = ()) -> World:
        """Pure projected world; existing async remap remains the legacy write seam."""
        from copy import deepcopy
        return deepcopy(world)

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        """Instantiate-time world-side remap (TZ §2).

        Registry pointers land on the *instance* member uids and entries
        still aimed at source members are repointed; the adapter's
        declared world-side ref fields (pick policies, layout-embedded
        structure refs) follow the same map. Runs inside the caller's
        transaction; ``members`` are this kind's freshly written
        instance members.
        """
