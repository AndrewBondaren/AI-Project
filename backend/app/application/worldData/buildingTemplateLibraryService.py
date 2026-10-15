"""Building template library — tz_building_generator §5–6 / WB-11.

Membership is the single availability source (B6): world-owned member
writes no longer append ``building_template_registry`` pointer rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.application.worldData.libraryPacks.writeResults import PolicyRequired

import logging

from app.application.importResult import ImportResult
from app.application.jsonValidation.resolve import ResolveContext, resolve_model, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.ids import LibraryKind, library_uid
from app.application.jsonValidation.worldRow import crops, livestock, resource_types
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.errors import WorldDataError
from app.application.worldData.worldService import WorldService
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.application.worldData.libraryPacks.legacyPack import (
    ensure_legacy_pack,
    legacy_member_row,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.db.database import Database
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository

logger = logging.getLogger(__name__)
_PLOT_ONLY_FIELDS = frozenset(PlotLayoutTemplate.model_fields) - frozenset(BuildingTemplateOutline.model_fields)


def building_template_uid(system_name: str) -> str:
    return library_uid(LibraryKind.BUILDING_TEMPLATES, system_name)


def _body_structure_type(body: BuildingTemplateOutline | PlotLayoutTemplate | BuildingTemplate) -> str | None:
    """Legacy denorm only; target building bodies store their structure UID in data."""
    if isinstance(body, BuildingTemplate):
        return None
    if isinstance(body, PlotLayoutTemplate):
        return str(body.plot_type.value)
    return body.structure_type


class BuildingTemplateLibraryService:

    def __init__(
        self,
        repo: IBuildingTemplateRepository,
        world_service: WorldService,
        *,
        db: Database | None = None,
        catalog: PackCatalogRepos | None = None,
        write_provider=None,
        ensure_provider=None,
    ) -> None:
        self._repo = repo
        self._worlds = world_service
        self._db = db
        self._catalog = catalog
        self._write_provider = write_provider
        self._ensure_provider = ensure_provider

    async def get_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self.find_by_uid(template_uid)

    async def list_all(self) -> list[BuildingTemplateRow]:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self._repo.list_all()

    async def find_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def write_body(self, body: BuildingTemplate, *, pack_uid, template_uid=None,
                         source_file=None, world_uid=None) -> BuildingTemplateRow:
        from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
        return await write_domain_body(self._write_provider(), LibraryKind.BUILDING_TEMPLATES,
            body, pack_uid=pack_uid, template_uid=template_uid,
            source_file=source_file, world_uid=world_uid)

    async def persist_prepared(self, outline, *, template_uid, source_file, added):
        from app.application.worldData.libraryPacks.preparedPersistence import persist_body_row
        row = BuildingTemplateRow(template_uid=template_uid, system_name=outline.system_name,
            display_name=outline.display_name, structure_type=_body_structure_type(outline),
            version=outline.version if isinstance(outline, BuildingTemplateOutline) else BuildingTemplateRow.version,
            data=outline.model_dump(mode="json"), source_file=source_file)
        return await persist_body_row(self._repo, row, added=added)

    async def delete_prepared(self, template_uid: str) -> None:
        from app.db.database import _in_transaction
        if not _in_transaction.get():
            raise RuntimeError("prepared deletion requires caller UOW")
        await self._repo.delete(template_uid)

    async def delete(self, template_uid: str, *, world_uid=None) -> None:
        if self._write_provider is not None:
            await self._write_provider().delete_member(template_uid, world_uid=world_uid)
            return
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        await self._repo.delete(template_uid)

    async def upsert_outline(
        self,
        outline: BuildingTemplateOutline | PlotLayoutTemplate,
        *,
        source_file: str | None = None,
        pack_uid: str | None = None,
        template_uid: str | None = None,
        world_uid: str | None = None,
    ) -> BuildingTemplateRow:
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
            return await write_domain_body(self._write_provider(), LibraryKind.BUILDING_TEMPLATES,
                outline, pack_uid=pack_uid, template_uid=template_uid, source_file=source_file, world_uid=world_uid)
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        uid = template_uid or library_uid(LibraryKind.BUILDING_TEMPLATES, outline.system_name, pack_uid=pack_uid)
        row = BuildingTemplateRow(
            template_uid=uid,
            system_name=outline.system_name,
            display_name=outline.display_name,
            structure_type=_body_structure_type(outline),
            # PlotLayoutTemplate carries no version — the row model default applies.
            version=getattr(outline, "version", BuildingTemplateRow.version),
            data=outline.model_dump(mode="json"),
            source_file=source_file,
        )
        await self._repo.upsert(row)
        return row

    async def import_bodies_into_world(
        self,
        world_uid: str,
        bodies: list[dict],
        *, decisions=(), preview_token=None,
    ) -> ImportResult | PolicyRequired:
        if not isinstance(bodies, list):
            raise BundleValidationError("building_templates section must be an array")
        if self._db is not None and self._write_provider is None:
            raise RuntimeError("SQL library imports require the common write service")
        if self._db is not None:
            async with self._db.transaction_if_needed():
                return await self._import_bodies(world_uid, bodies, decisions=decisions, preview_token=preview_token)
        return await self._import_bodies(world_uid, bodies, decisions=decisions, preview_token=preview_token)

    async def _import_bodies(
        self,
        world_uid: str,
        bodies: list[dict],
        *, decisions=(), preview_token=None,
    ) -> ImportResult | PolicyRequired:
        """Manifest-less bodies → world-owned ``legacy`` pack members (plan step 3)."""
        if not bodies:
            return ImportResult(total=0, succeeded=0, failed=0, errors=[])
        if self._catalog is None:
            raise RuntimeError(
                "BuildingTemplateLibraryService: pack catalog repositories are not wired"
            )
        world = await self._worlds.get_by_id(world_uid)
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.writeResults import WriteResult
            prepared = [self.prepare_body(world, raw) for raw in bodies]
            result = await self._write_provider().import_legacy_bodies(
                LibraryKind.BUILDING_TEMPLATES, world_uid, prepared,
                decisions=decisions, preview_token=preview_token)
            if not isinstance(result, WriteResult):
                return result
            return ImportResult(total=len(bodies), succeeded=len(bodies), failed=0, errors=[])
        legacy = await ensure_legacy_pack(world_uid, self._catalog.packs)
        succeeded = 0
        errors = []
        for i, raw in enumerate(bodies):
            try:
                outline = self.prepare_body(world, raw)
                await self.upsert_outline(
                    outline, source_file="bundle", pack_uid=legacy.pack_uid, world_uid=world_uid
                )
                await self._catalog.members.insert_missing([
                    legacy_member_row(
                        LibraryKind.BUILDING_TEMPLATES, outline.system_name,
                        world_uid=world_uid,
                    ),
                ])
                succeeded += 1
            except WorldDataError:
                raise  # domain failure is not a row-level validation error
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
        """Flat bundle bodies of building members owned by ``world_uid`` (B6).

        Availability comes from pack membership (``owner_world_uid``), not
        from the legacy registry column; a member without a body row is a
        hard reference error, same as the old missing-pointer path.
        """
        if self._catalog is None:
            raise RuntimeError(
                "BuildingTemplateLibraryService: pack catalog repositories are not wired"
            )
        members = await self._catalog.members.list_for_world(world_uid)
        bodies: list[dict] = []
        for member in members:
            if member.library_kind != LibraryKind.BUILDING_TEMPLATES.value:
                continue
            row = await self._repo.get_by_uid(member.template_uid)
            if row is None:
                ctx = ResolveContext(path_prefix=("building_templates", member.template_uid))
                reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "library reference unavailable", code="REF_W_UNKNOWN")])
            bodies.append(dict(row.data))
        return bodies
