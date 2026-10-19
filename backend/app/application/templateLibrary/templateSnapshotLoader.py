"""World template snapshot loader — the async boundary of packing (B3).

Reads the world's membership-scoped ``EffectiveCatalog`` (5a), prepares
typed bodies through the domain adapters and returns one immutable
``WorldTemplateSnapshot`` keyed by member ``template_uid``. Sync
generators/planners receive the snapshot-derived catalogs and never touch
SQL or the filesystem.

Boundary duties (TZ packs §5/§7, domain libraries §5):
- availability = membership only; pins are author-usage markers and never
  narrow candidates; members owned by another world are absent here;
- every member is validated once at this boundary — graph issues are
  reported through the shared ``log_issues`` warning channel, one
  diagnostic per event; members with a missing/invalid body or a
  dangling declared ref are excluded so downstream planning sees a
  closed graph.
  Runtime never substitutes an arbitrary candidate (TZ §5): domains with
  a declared default layer apply their POJO default, domains without one
  (relief, R21) reject.

Each public call resolves its own catalog — ``load`` and
``load_relief`` are independent reads, not one atomic snapshot: a
membership write between them is visible to the second. Callers that
need one consistent view must share a single returned snapshot.
"""

from __future__ import annotations

import logging

from app.application.jsonValidation.resolve import log_issues
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingScope,
    PackingStep,
    packing_warning,
)
from app.application.templateLibrary.packs.effectiveCatalog import (
    EffectiveCatalogLoader,
)
from app.application.templateLibrary.packs.lifecycleContracts import CatalogSnapshot
from app.application.templateLibrary.packs.templateGraphValidation import (
    prepare_template_graph,
)
from app.application.templateLibrary.templateContracts import (
    ReliefTemplateSnapshot,
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
from app.db.models.world import World
from app.ids import LibraryKind

logger = logging.getLogger(__name__)

_SNAPSHOT_KINDS = (
    LibraryKind.PLOT_TEMPLATES,
    LibraryKind.BUILDING_TEMPLATES,
    LibraryKind.STRUCTURE_TEMPLATES,
)


class TemplateSnapshotLoader:
    """Container seam: ``EffectiveCatalogLoader`` → validated snapshot."""

    def __init__(self, catalog_loader: EffectiveCatalogLoader) -> None:
        self._loader = catalog_loader

    async def _prepare(
        self,
        world: World,
        kinds: tuple[LibraryKind, ...],
    ) -> dict:
        catalog = await self._loader.load(world.world_uid)
        members = {
            member.template_uid: member
            for kind in kinds
            for member in catalog.candidates(kind)
        }
        bodies: dict[str, dict] = {}
        for uid in members:
            raw = await catalog.body(uid)
            if raw is not None:
                bodies[uid] = raw
        graph = prepare_template_graph(
            CatalogSnapshot(members, bodies, {}), world=world,
        )
        if graph.issues:
            log_issues(graph.issues)

        # Drop members whose declared refs resolve to absent/excluded
        # bodies — a missing dependency stays a diagnosed gap, not a
        # district-wide generation error. Declared refs only target
        # ref-free structure kinds (template_body_refs contract), so a
        # single pass is closed under exclusion.
        excluded = {
            ref.consumer for ref in graph.refs
            if ref.template_uid not in graph.bodies
        }
        return {
            uid: (members[uid], body)
            for uid, body in graph.bodies.items()
            if uid not in excluded
        }

    async def load_relief(self, world: World) -> ReliefTemplateSnapshot:
        """Membership-scoped relief members → typed bodies (B5).

        Independent read — not atomic with ``load`` (see class docstring).
        Bodies are guaranteed ``ReliefTemplate`` by ``_prepare`` — the
        RELIEF kind is only ever prepared by ``ReliefBodyPreparation``.
        """
        prepared = await self._prepare(world, (LibraryKind.RELIEF_TEMPLATES,))
        return ReliefTemplateSnapshot(
            world_uid=str(world.world_uid),
            templates={
                uid: TemplateEntry(
                    template_uid=uid, pack_uid=member.pack_uid, body=body,
                )
                for uid, (member, body) in prepared.items()
            },
        )

    async def load(self, world: World) -> WorldTemplateSnapshot:
        prepared = await self._prepare(world, _SNAPSHOT_KINDS)

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
                    district=PackingScope.SNAPSHOT,
                    system_name=uid,
                    reason=PackingReason.PLOT_TYPE_DEFAULTED,
                )

        return WorldTemplateSnapshot(
            world_uid=str(world.world_uid),
            plots=plots,
            buildings=entries_of(LibraryKind.BUILDING_TEMPLATES, BuildingTemplate),
            structures=entries_of(LibraryKind.STRUCTURE_TEMPLATES, StructureTemplate),
        )
