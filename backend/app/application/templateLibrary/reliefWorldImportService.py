"""Import relief templates into a world — membership + R34 terrain upsert.

Bodies arriving through a manifest-less bundle section become members of the
world-owned ``legacy`` pack (plan library-packs-model step 3 / TZ §1.1).
Membership is the single availability source — the legacy
``relief_template_registry`` world column was removed in B7. API/routes stay
thin.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.application.worldData.libraryPacks.writeResults import PolicyRequired

from app.application.jsonValidation.resolve import ResolveContext, resolve_model

from app.application.worldData.bundle import SOURCE_FILE_BUNDLE
from app.application.worldData.reliefTerrainSync import (
    merge_missing_terrain_entries,
)
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.legacyPack import (
    ensure_legacy_pack,
    legacy_member_row,
)
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefWorldRefValidation import (
    validate_relief_world_refs,
)
from app.application.worldData.worldColumnWrite import apply_world_column
from app.application.worldData.worldLookup import require_world
from app.db.repositories.iWorldRepository import IWorldRepository
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.db.database import Database
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.reliefTemplate import ReliefTemplateRow


class ReliefWorldImportService:

    def __init__(
        self,
        world_repository: IWorldRepository,
        library: ReliefTemplateLibraryService,
        *,
        catalog: PackCatalogRepos,
        write_provider=None,
        db: Database | None = None,
    ) -> None:
        self._worlds = world_repository
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
        world = await require_world(self._worlds, world_uid)
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
                source_file=SOURCE_FILE_BUNDLE,
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
        """World-side barrier/canal checks — invoked only on the
        write/import seam (``ReliefPackAdapter.prepare_body``); the
        read boundary never reaches it (B7 review, variant B)."""
        validate_relief_world_refs(world, outline)

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
        world = await require_world(self._worlds, world_uid)
        projected = deepcopy(world)
        added = merge_missing_terrain_entries(
            projected,
            needed,
            source="relief_import",
            template_uid=template_uid,
            system_name=outline.system_name,
        )
        if added:
            apply_world_column(world, "terrain_registry", projected.terrain_registry, ResolveContext())
            await self._worlds.update(world)
