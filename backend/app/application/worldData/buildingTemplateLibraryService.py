"""Building template library + world registry bind — tz_building_generator §5–6 / WB-11."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.application.importResult import ImportResult
from app.application.jsonValidation.resolve import ResolveContext, resolve_model, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.application.jsonValidation.worldRow import building_template_registry
from app.application.jsonValidation.sourceValidation import validate_source
from app.ids import LibraryKind, library_uid
from app.application.jsonValidation.worldRow import crops, livestock, resource_types
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.worldService import WorldService
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
    plot_type_defaulted,
)
from app.dataModel.locations.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.locations.structure.building.buildingTemplateRegistryEntry import (
    BuildingTemplateRegistryEntry,
)
from app.application.worldData.libraryPacks.legacyPack import (
    ensure_legacy_pack,
    legacy_member_row,
)
from app.db.database import Database, _in_transaction
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository

logger = logging.getLogger(__name__)
_PLOT_ONLY_FIELDS = frozenset(PlotLayoutTemplate.model_fields) - frozenset(BuildingTemplateOutline.model_fields)


def building_template_uid(system_name: str) -> str:
    return library_uid(LibraryKind.BUILDING_TEMPLATES, system_name)


def _registry_entries(world) -> list[BuildingTemplateRegistryEntry]:
    return list(building_template_registry(world).root)


def _body_structure_type(body) -> str:
    """Row denorm: outline's primary purpose, or the plot's family (plot bodies)."""
    value = getattr(body, "structure_type", None)
    if value is None:
        value = getattr(body, "plot_type", "")
    return str(getattr(value, "value", value))


class BuildingTemplateLibraryService:

    def __init__(
        self,
        repo: IBuildingTemplateRepository,
        world_service: WorldService,
        *,
        db: Database | None = None,
        packs: ILibraryPackRepository | None = None,
        members: ILibraryPackMemberRepository | None = None,
    ) -> None:
        self._repo = repo
        self._worlds = world_service
        self._db = db
        self._packs = packs
        self._members = members

    async def layouts_for_world(self, world) -> list[PlotLayoutTemplate]:
        """Hydrate plot bodies; valid outline-only bodies have no packing layout."""

        from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
            PackingReason,
            PackingStep,
            packing_warning,
        )

        layouts: list[PlotLayoutTemplate] = []
        world_uid = getattr(world, "world_uid", "?")
        for entry in _registry_entries(world):
            row = await self._repo.get_by_uid(entry.system_template_uid)
            ctx = ResolveContext(path_prefix=("building_template_registry", entry.system_template_uid))
            if row is None:
                reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "library reference unavailable", code="REF_W_UNKNOWN")])
            body = self.parse_body(row.data, ctx=ctx)
            if isinstance(body, BuildingTemplateOutline):
                continue
            layout = body
            validate_source(world, layout, ctx=ctx)
            if plot_type_defaulted(layout):
                packing_warning(
                    PackingStep.CACHE,
                    district="library",
                    system_name=layout.system_name,
                    reason=PackingReason.PLOT_TYPE_DEFAULTED,
                )
            layouts.append(layout)
        return layouts

    async def find_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def upsert_outline(
        self,
        outline: BuildingTemplateOutline,
        *,
        source_file: str | None = None,
        pack_uid: str | None = None,
    ) -> BuildingTemplateRow:
        uid = library_uid(LibraryKind.BUILDING_TEMPLATES, outline.system_name, pack_uid=pack_uid)
        row = BuildingTemplateRow(
            template_uid=uid,
            system_name=outline.system_name,
            display_name=outline.display_name,
            structure_type=_body_structure_type(outline),
            version=outline.version,
            data=outline.model_dump(mode="json"),
            source_file=source_file,
        )
        await self._repo.upsert(row)
        return row

    async def import_bodies_into_world(
        self,
        world_uid: str,
        bodies: list[dict],
    ) -> ImportResult:
        if not isinstance(bodies, list):
            raise BundleValidationError("building_templates section must be an array")
        if self._db is not None and not _in_transaction.get():
            async with self._db.transaction():
                return await self._import_bodies(world_uid, bodies)
        return await self._import_bodies(world_uid, bodies)

    async def _import_bodies(
        self,
        world_uid: str,
        bodies: list[dict],
    ) -> ImportResult:
        """Manifest-less bodies → world-owned ``legacy`` pack members (plan step 3)."""
        if self._packs is None or self._members is None:
            raise RuntimeError(
                "BuildingTemplateLibraryService: pack catalog repositories are not wired"
            )
        world = await self._worlds.get_by_id(world_uid)
        legacy = await ensure_legacy_pack(world_uid, self._packs)
        succeeded = 0
        errors = []
        for i, raw in enumerate(bodies):
            try:
                outline = self.prepare_body(world, raw)
                row = await self.upsert_outline(
                    outline, source_file="bundle", pack_uid=legacy.pack_uid
                )
                await self._members.insert_missing([
                    legacy_member_row(
                        LibraryKind.BUILDING_TEMPLATES, outline.system_name,
                        world_uid=world_uid,
                    ),
                ])
                await self._ensure_registry(world_uid, row)
                succeeded += 1
            except ValueError as exc:
                from app.application.importResult import ImportError
                errors.append(ImportError(index=i, message=str(exc)))
        return ImportResult(
            total=len(bodies),
            succeeded=succeeded,
            failed=len(errors),
            errors=errors,
        )

    @staticmethod
    def parse_body(raw: dict, *, ctx: ResolveContext) -> BuildingTemplateOutline | PlotLayoutTemplate:
        """Use declared plot fields to distinguish the two supported wire shapes."""
        model = PlotLayoutTemplate if isinstance(raw, dict) and _PLOT_ONLY_FIELDS.intersection(raw) else BuildingTemplateOutline
        return resolve_model(model, raw, ctx=ctx)

    @staticmethod
    def subject_issues(world, body) -> list:
        """resource/crops/livestock subject violations of a template body."""
        issues = resource_types(world).check_template_subjects(body.resource_kind, body.subjects)
        if not issues:
            issues = crops(world).check_template_subjects(body.crop_kind, body.subjects)
        if not issues:
            issues = livestock(world).check_template_subjects(body.livestock_kind, body.subjects)
        return issues

    @staticmethod
    def prepare_body(world, raw: dict, *, ctx: ResolveContext | None = None) -> BuildingTemplateOutline:
        active_ctx = ctx if ctx is not None else ResolveContext(path_prefix=("building_templates",))
        outline = resolve_model(BuildingTemplateOutline, raw, ctx=active_ctx)
        issues = BuildingTemplateLibraryService.subject_issues(world, outline)
        if issues:
            token, code = issues[0]
            reject_unresolved(active_ctx, [FieldPathError(active_ctx.path_prefix + ("subjects",),
                f"{code}: extract/farm/livestock subject {token!r}", code=code)])
        return outline

    async def export_bodies_for_world(self, world_uid: str) -> list[dict]:
        world = await self._worlds.get_by_id(world_uid)
        bodies: list[dict] = []
        for entry in _registry_entries(world):
            row = await self._repo.get_by_uid(entry.system_template_uid)
            if row is None:
                ctx = ResolveContext(path_prefix=("building_template_registry", entry.system_template_uid))
                reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "library reference unavailable", code="REF_W_UNKNOWN")])
            ctx = ResolveContext(path_prefix=("building_template_registry", entry.system_template_uid))
            body = self.parse_body(row.data, ctx=ctx)
            if isinstance(body, PlotLayoutTemplate):
                validate_source(world, body, ctx=ctx)
            bodies.append(dict(row.data))
        return bodies

    async def _ensure_registry(self, world_uid: str, row: BuildingTemplateRow) -> None:
        world = await self._worlds.get_by_id(world_uid)
        entries = _registry_entries(world)
        if any(e.system_template_uid == row.template_uid for e in entries):
            return
        entries.append(
            BuildingTemplateRegistryEntry(
                system_template_uid=row.template_uid,
                display_template_name=row.display_name,
                imported_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await self._worlds.update(
            world_uid,
            {
                "building_template_registry": [
                    e.model_dump(mode="json") for e in entries
                ],
            },
        )
