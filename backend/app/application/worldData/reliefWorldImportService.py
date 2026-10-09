"""Import relief templates into a world — R34 terrain upsert + registry pointers.

Bodies arriving through a manifest-less bundle section become members of the
world-owned ``legacy`` pack (plan library-packs-model step 3 / TZ §1.1);
transitional dual-write keeps ``relief_template_registry`` pointers pointing
at the world-owned member uids (step 4a contract). API/routes stay thin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from app.application.jsonValidation.resolve import ResolveContext, resolve_model

from app.application.worldData.generators.terrain.relief.log.log import relief_warning
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
from app.dataModel.terrain.relief.reliefTemplateRegistryEntry import (
    ReliefTemplateRegistryEntry,
)
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.application.jsonValidation.worldRow import (
    barrier_templates,
    canal_templates,
    relief_template_registry,
    terrain,
)
from app.application.worldData.generators.terrain.relief.canal.outlineCollect import (
    collect_outline_structure_canal_refs,
    collect_outline_structure_refs,
)
from app.db.database import Database, _in_transaction
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository


class ReliefWorldImportService:

    def __init__(
        self,
        world_service: WorldService,
        library: ReliefTemplateLibraryService,
        *,
        packs: ILibraryPackRepository,
        members: ILibraryPackMemberRepository,
        db: Database | None = None,
    ) -> None:
        self._worlds = world_service
        self._library = library
        self._packs = packs
        self._members = members
        self._db = db

    async def import_outlines_into_world(
        self,
        world_uid: str,
        outlines: list[dict],
    ) -> dict:
        """Bodies → world-owned ``legacy`` members + registry pointers + R34 sync."""
        if self._db is not None and not _in_transaction.get():
            async with self._db.transaction():
                return await self._import_outlines(world_uid, outlines)
        return await self._import_outlines(world_uid, outlines)

    async def _import_outlines(
        self,
        world_uid: str,
        outlines: list[dict],
    ) -> dict:
        world = await self._worlds.get_by_id(world_uid)
        legacy = await ensure_legacy_pack(world_uid, self._packs)
        imported_uids: list[str] = []
        for raw in outlines:
            outline = self.prepare_body(world, raw)
            row = await self._library.upsert_outline(
                outline, source_file="bundle", pack_uid=legacy.pack_uid
            )
            await self._members.insert_missing([
                legacy_member_row(
                    LibraryKind.RELIEF_TEMPLATES, outline.system_name,
                    world_uid=world_uid,
                ),
            ])
            imported_uids.append(row.template_uid)
            await self._ensure_registry_pointer(world_uid, row.template_uid, outline)
            await self._sync_terrain_from_outline(world_uid, outline, row.template_uid)

        return {"imported": len(imported_uids), "uids": imported_uids}

    def prepare_body(self, world, raw: dict, *, ctx: ResolveContext | None = None) -> ReliefTemplate:
        outline = resolve_model(ReliefTemplate, raw, ctx=ctx)
        warn_template_invalid_geom(outline)
        barrier_keys = {e.system_type for e in barrier_templates(world).root}
        self._validate_structure_refs(outline, barrier_keys)
        self._validate_structure_canal(outline, world)
        return outline

    async def import_library_uid_into_world(
        self,
        world_uid: str,
        template_uid: str,
    ) -> dict:
        """Attach an engine-library template as a world-owned ``legacy`` member.

        Interim until step 4b ``instantiate_pack``: the body copies into the
        world's legacy pack (pointer must target a world-owned member), with
        the engine uid kept as ``source_template_uid`` provenance.
        """
        if self._db is not None and not _in_transaction.get():
            async with self._db.transaction():
                return await self._import_library_uid(world_uid, template_uid)
        return await self._import_library_uid(world_uid, template_uid)

    async def _import_library_uid(
        self,
        world_uid: str,
        template_uid: str,
    ) -> dict:
        row = await self._library.get_by_uid(template_uid)
        outline = resolve_model(ReliefTemplate, row.data, label=template_uid)
        warn_template_invalid_geom(outline, template_uid=template_uid)
        world = await self._worlds.get_by_id(world_uid)
        barrier_keys = {
            e.system_type for e in barrier_templates(world).root
        } if barrier_templates(world).root else set()
        self._validate_structure_refs(outline, barrier_keys)
        self._validate_structure_canal(outline, world)
        legacy = await ensure_legacy_pack(world_uid, self._packs)
        new_row = await self._library.upsert_outline(
            outline,
            source_file=row.source_file or "library",
            pack_uid=legacy.pack_uid,
        )
        await self._members.insert_missing([
            LibraryPackMemberRow(
                template_uid=new_row.template_uid,
                pack_uid=legacy.pack_uid,
                library_kind=LibraryKind.RELIEF_TEMPLATES.value,
                local_uid=outline.system_name,
                source_template_uid=row.template_uid,
            ),
        ])
        await self._ensure_registry_pointer(world_uid, new_row.template_uid, outline)
        await self._sync_terrain_from_outline(world_uid, outline, new_row.template_uid)
        return {"imported": 1, "uids": [new_row.template_uid]}

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

    async def _ensure_registry_pointer(
        self,
        world_uid: str,
        template_uid: str,
        outline: ReliefTemplate,
    ) -> None:
        world = await self._worlds.get_by_id(world_uid)
        reg = relief_template_registry(world)
        if reg.entry_for_uid(template_uid) is not None:
            return
        entries = list(reg.root)
        entries.append(
            ReliefTemplateRegistryEntry(
                system_template_uid=template_uid,
                display_template_name=outline.display_name,
                context=outline.context,
                imported_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await self._worlds.update(
            world_uid,
            {"relief_template_registry": [e.model_dump(mode="json") for e in entries]},
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
        current = terrain(world)
        have = {e.system_terrain for e in current.root}
        canon = {
            e.system_terrain: e
            for e in WorldTerrainRegistry.canonical_engine().root
        }
        added: list[str] = []
        new_rows = list(current.root)
        for key in sorted(needed):
            if key in have:
                continue
            entry = canon.get(key)
            if entry is None:
                # closed ReliefConditionTerrain should always be in engine set
                continue
            new_rows.append(entry)
            added.append(key)
            relief_warning(
                "r34_terrain_upsert",
                world_uid=world_uid,
                system_terrain=key,
                source="relief_import",
                template_uid=template_uid,
                system_name=outline.system_name,
            )
        if added:
            await self._worlds.update(
                world_uid,
                {"terrain_registry": [e.model_dump(mode="json") for e in new_rows]},
            )
