"""World template snapshot loader — the async boundary of packing (B3).

Reads the world's membership-scoped ``EffectiveCatalog`` (5a), prepares
typed bodies through the domain adapters and returns one immutable
``WorldTemplateSnapshot`` keyed by member ``template_uid``. Sync
generators/planners receive the snapshot-derived catalogs and never touch
SQL, the filesystem or the legacy world registries.

Boundary duties (TZ packs §5/§7, domain libraries §5):
- availability = membership only; pins are author-usage markers and never
  narrow candidates; members owned by another world are absent here;
- every member is validated once at this boundary — graph issues are
  reported through the shared ``report_issues`` channel, one diagnostic
  per event; members with a missing/invalid body or a dangling declared
  ref are excluded so downstream planning sees a closed graph.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from app.application.jsonValidation.resolve import ResolveContext, report_issues
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_warning,
)
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import (
    TemplatePreparationError,
)
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    PackDomainAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    template_body_refs,
)
from app.application.worldData.libraryPacks.effectiveCatalog import (
    EffectiveCatalogLoader,
)
from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot
from app.application.worldData.libraryPacks.templateGraphValidation import (
    template_graph_issues,
)
from app.application.worldData.templateContracts import (
    TemplateEntry,
    WorldTemplateSnapshot,
)
from app.dataModel.locations.structure.building.buildingTemplate import (
    BuildingTemplate,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
    plot_type_defaulted,
)
from app.dataModel.locations.structure.building.structureTemplate import (
    StructureTemplate,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind

logger = logging.getLogger(__name__)

_SNAPSHOT_KINDS = (
    LibraryKind.PLOT_TEMPLATES,
    LibraryKind.BUILDING_TEMPLATES,
    LibraryKind.STRUCTURE_TEMPLATES,
)


class TemplateSnapshotLoader:
    """Container seam: ``EffectiveCatalogLoader`` + the domain adapter map."""

    def __init__(
        self,
        catalog_loader: EffectiveCatalogLoader,
        adapters: Mapping[LibraryKind, PackDomainAdapter],
    ) -> None:
        self._loader = catalog_loader
        self._adapters = adapters

    async def load(self, world: World) -> WorldTemplateSnapshot:
        catalog = await self._loader.load(world.world_uid)
        members = {
            member.template_uid: member
            for kind in _SNAPSHOT_KINDS
            for member in catalog.candidates(kind)
        }
        bodies: dict[str, dict] = {}
        for uid in members:
            raw = await catalog.body(uid)
            if raw is not None:
                bodies[uid] = raw
        issues = template_graph_issues(
            CatalogSnapshot(members, bodies, {}), world=world,
        )
        if issues:
            report_issues(ResolveContext(), issues)

        prepared: dict[str, tuple[LibraryPackMemberRow, object]] = {}
        for uid, member in members.items():
            raw = bodies.get(uid)
            if raw is None:
                continue  # already diagnosed by template_graph_issues
            adapter = self._adapters.get(LibraryKind(member.library_kind))
            try:
                body = adapter.prepare_body(
                    raw,
                    local_uid=member.local_uid,
                    template_uid=uid,
                    world=world,
                )
            except TemplatePreparationError:
                continue  # already diagnosed by template_graph_issues
            prepared[uid] = (member, body)

        # Drop members whose declared refs resolve to absent/excluded
        # bodies — a missing dependency stays a diagnosed gap, not a
        # district-wide generation error. Refs only point plot/building →
        # structure, so a single pass is closed under exclusion.
        for uid in list(prepared):
            member, body = prepared[uid]
            for ref in template_body_refs(
                LibraryKind(member.library_kind), body, uid,
            ):
                if ref.template_uid not in prepared:
                    del prepared[uid]
                    break

        def entries_of(kind: LibraryKind, model: type) -> dict[str, TemplateEntry]:
            out = {}
            for uid, (member, body) in prepared.items():
                if member.library_kind != kind.value or not isinstance(body, model):
                    continue
                out[uid] = TemplateEntry(
                    template_uid=uid, pack_uid=member.pack_uid, body=body,
                )
            return out

        plots = entries_of(LibraryKind.PLOT_TEMPLATES, PlotLayoutTemplate)
        for uid, entry in plots.items():
            if plot_type_defaulted(entry.body):
                packing_warning(
                    PackingStep.CACHE,
                    district="snapshot",
                    system_name=uid,
                    reason=PackingReason.PLOT_TYPE_DEFAULTED,
                )

        return WorldTemplateSnapshot(
            world_uid=str(world.world_uid),
            plots=plots,
            buildings=entries_of(LibraryKind.BUILDING_TEMPLATES, BuildingTemplate),
            structures=entries_of(LibraryKind.STRUCTURE_TEMPLATES, StructureTemplate),
        )
