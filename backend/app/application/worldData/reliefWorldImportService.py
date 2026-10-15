"""Import relief templates into a world — membership + R34 terrain upsert.

Bodies arriving through a manifest-less bundle section become members of the
world-owned ``legacy`` pack (plan library-packs-model step 3 / TZ §1.1).
Membership is the single availability source — the legacy
``relief_template_registry`` world column was removed in B7. API/routes stay
thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.application.worldData.libraryPacks.writeResults import PolicyRequired

from app.application.jsonValidation.resolve import ResolveContext, resolve_model

from app.application.worldData.reliefTerrainSync import (
    merge_missing_terrain_entries,
)
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.legacyPack import (
    ensure_legacy_pack,
    legacy_member_row,
)
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.worldService import WorldService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.application.jsonValidation.worldRow import (
    barrier_templates,
    canal_templates,
)
from app.application.worldData.generators.terrain.relief.canal.outlineCollect import (
    collect_outline_structure_canal_refs,
    collect_outline_structure_refs,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.db.database import Database
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.reliefTemplate import ReliefTemplateRow


class ReliefWorldImportService:

    def __init__(
        self,
        world_service: WorldService,
        library: ReliefTemplateLibraryService,
        *,
        catalog: PackCatalogRepos,
        write_provider=None,
        db: Database | None = None,
    ) -> None:
        self._worlds = world_service
        self._library = library
        self._catalog = catalog
        self._write_provider = write_provider
        self._db = db

    async def import_outlines_into_world(
        self,
        world_uid: str,
        outlines: list[dict],
        *, decisions=(), preview_token=None,
    ) -> dict | PolicyRequired:
        """Bodies → world-owned ``legacy`` members + R34 sync."""
        if self._db is not None and self._write_provider is None:
            raise RuntimeError("SQL library imports require the common write service")
        if self._db is not None:
            async with self._db.transaction_if_needed():
                return await self._import_outlines(world_uid, outlines, decisions=decisions, preview_token=preview_token)
        return await self._import_outlines(world_uid, outlines, decisions=decisions, preview_token=preview_token)

    async def _import_outlines(
        self,
        world_uid: str,
        outlines: list[dict],
        *, decisions=(), preview_token=None,
    ) -> dict | PolicyRequired:
        world = await self._worlds.get_by_id(world_uid)
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.writeResults import WriteResult
            prepared = [self.prepare_body(world, raw) for raw in outlines]
            if not prepared:
                return {"imported": 0, "uids": []}
            result = await self._write_provider().import_legacy_bodies(
                LibraryKind.RELIEF_TEMPLATES, world_uid, prepared,
                decisions=decisions, preview_token=preview_token)
            if not isinstance(result, WriteResult):
                return result
            uids = [write.value.member.template_uid for item in result.plan.items for write in item.members]
            return {"imported": len(uids), "uids": uids}
        imported_uids: list[str] = []
        for raw in outlines:
            outline = self.prepare_body(world, raw)
            row = await self._attach_member(
                world_uid,
                outline,
                source_file="bundle",
                member=legacy_member_row(
                    LibraryKind.RELIEF_TEMPLATES, outline.system_name,
                    world_uid=world_uid,
                ),
            )
            imported_uids.append(row.template_uid)

        return {"imported": len(imported_uids), "uids": imported_uids}

    async def _attach_member(
        self,
        world_uid: str,
        outline: ReliefTemplate,
        *,
        source_file: str,
        member: LibraryPackMemberRow,
    ) -> ReliefTemplateRow:
        """Body → world-owned ``legacy`` member + R34 sync."""
        legacy = await ensure_legacy_pack(world_uid, self._catalog.packs)
        row = await self._library.upsert_outline(
            outline, source_file=source_file, pack_uid=legacy.pack_uid, world_uid=world_uid
        )
        await self._catalog.members.insert_missing([member])
        await self._sync_terrain_from_outline(world_uid, outline, row.template_uid)
        return row

    def prepare_body(
        self,
        world,
        raw: dict,
        *,
        ctx: ResolveContext | None = None,
        template_uid: str | None = None,
    ) -> ReliefTemplate:
        outline = resolve_model(ReliefTemplate, raw, ctx=ctx)
        warn_template_invalid_geom(outline, template_uid=template_uid)
        self.validate_world_refs(world, outline)
        return outline

    def validate_world_refs(self, world, outline: ReliefTemplate) -> None:
        """World-side barrier/canal checks — the ``validate_world`` seam of
        ``ReliefBodyPreparation`` (B6 review step 6)."""
        barrier_keys = {e.system_type for e in barrier_templates(world).root}
        self._validate_structure_refs(outline, barrier_keys)
        self._validate_structure_canal(outline, world)

    def _validate_structure_refs(
        self,
        outline: ReliefTemplate,
        barrier_keys: set[str],
    ) -> None:
        refs = collect_outline_structure_refs(outline)
        if not refs:
            return
        if not barrier_keys:
            raise ReliefValidationError(
                "structure_refs present but barrier_template_registry is empty: "
                f"{sorted(refs)}",
            )
        unknown = sorted(refs - barrier_keys)
        if unknown:
            raise ReliefValidationError(
                f"structure_refs unknown in barrier_template_registry: {unknown}",
            )

    def _validate_structure_canal(
        self,
        outline: ReliefTemplate,
        world: object,
    ) -> None:
        """``structure_canal`` ∈ ``canal_template_registry``; nested barrier refs."""
        canal_refs = collect_outline_structure_canal_refs(outline)
        if not canal_refs:
            return
        reg = canal_templates(world)
        known = {e.system_type for e in reg.root}
        unknown = sorted(canal_refs - known)
        if unknown:
            raise ReliefValidationError(
                f"structure_canal unknown in canal_template_registry: {unknown}",
            )
        barrier_keys = {e.system_type for e in barrier_templates(world).root}
        nested: set[str] = set()
        for ref in canal_refs:
            entry = reg.entry_for(ref)
            if entry is None or entry.structure is None:
                continue
            nested.update(entry.structure.structure_refs)
        if not nested:
            return
        if not barrier_keys:
            raise ReliefValidationError(
                "canal structure_refs present but barrier_template_registry "
                f"is empty: {sorted(nested)}",
            )
        bad = sorted(nested - barrier_keys)
        if bad:
            raise ReliefValidationError(
                "canal_template_registry.structure.structure_refs unknown "
                f"in barrier_template_registry: {bad}",
            )

    async def _sync_terrain_from_outline(
        self,
        world_uid: str,
        outline: ReliefTemplate,
        template_uid: str,
    ) -> None:
        """R34: upsert missing terrain_registry keys from conditions; WARNING log."""
        needed = {c.terrain.value for c in outline.conditions}
        if not needed:
            return
        world = await self._worlds.get_by_id(world_uid)
        added = merge_missing_terrain_entries(
            world,
            needed,
            source="relief_import",
            template_uid=template_uid,
            system_name=outline.system_name,
        )
        if added:
            await self._worlds.update(
                world_uid, {"terrain_registry": world.terrain_registry}
            )
