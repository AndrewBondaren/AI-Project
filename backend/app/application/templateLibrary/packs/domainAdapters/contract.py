"""Domain adapter contract of the pack application service — plan steps
4a–4c/5b, TZ §0.2/§2.

The universal pack layer (``packService``) owns identity, ownership and
atomicity; each adapter owns the body model, domain restrictions and its
declared world-side reference fields. Membership is the single runtime
availability source (B6): no adapter writes registry pointer rows —
projected-world remaps only rewrite pins, pick policies and embedded
body references. The legacy registry columns are gone (B7); their old
wire is read only inside the explicit migration boundary.

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
from typing import ClassVar

from app.application.templateLibrary.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.templateLibrary.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.templateLibrary.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.application.templateLibrary.plotTemplateLibraryService import PlotTemplateLibraryService
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind
from app.application.templateLibrary.packs.lifecycleContracts import FallbackDecision, MemberRef

DomainLibrary = (
    ReliefTemplateLibraryService
    | StructureTemplateLibraryService
    | BuildingTemplateLibraryService
    | PlotTemplateLibraryService
)

DomainOutline = (
    ReliefTemplate
    | StructureTemplate
    | PlotLayoutTemplate
    | BuildingTemplate
)

SYSTEM_NAME_FIELD = "system_name"
"""``StructureTemplate.system_name`` wire key — the model-A member uid."""


@dataclass(frozen=True)
class RemappedMember:
    """Instance member + its parsed outline — ``prepare_world_refs`` input."""
    member: LibraryPackMemberRow
    outline: DomainOutline


class PackDomainAdapter(ABC):
    """Body contract of one ``library_kind`` for the pack service.

    All methods run inside the caller's transaction — an adapter never owns
    atomicity. Declared body/world references feed the common usage index;
    the lifecycle job decides retention and deletion.
    """

    library_kind: ClassVar[LibraryKind]

    async def find_body_row(self, template_uid: str):
        """Legacy row-returning facade seam; common pipeline uses typed outlines."""
        raise NotImplementedError

    async def persist_prepared(self, outline: DomainOutline, *, member: LibraryPackMemberRow,
                               source_file: str | None, added: bool) -> None:
        """Persist validated typed data with explicit insert/update, in caller UOW."""
        raise NotImplementedError("domain has no prepared persistence")

    @abstractmethod
    def prepare_body(self, raw: dict, *, local_uid: str, template_uid: str,
                     world: World | None = None) -> DomainOutline:
        """Pure validation/normalization shared by preview and persistence."""

    def body_refs(self, body: dict, consumer: str) -> tuple[MemberRef, ...]:
        return ()

    def world_refs(self, world: World) -> tuple[MemberRef, ...]:
        return ()


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

        Members with a missing/invalid body or a dangling declared ref
        are excluded earlier, at the snapshot read boundary
        (``TemplateSnapshotLoader``, one ``report_issues`` record each —
        TZ §5, уточнение 2026-10-15): an arbitrary candidate is never
        substituted at any layer.
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
                           members: Sequence[RemappedMember]) -> World:
        """Pure projected world with remapped pins and declared ref fields.

        ``WriteRetentionPlanner`` applies the columns this projection
        changed; registry pointer rows are never touched (B6).
        """
        from copy import deepcopy
        return deepcopy(world)
