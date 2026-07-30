"""Import relief templates into a world — R34 terrain upsert + registry pointers.

API/routes stay thin; this service owns catalog sync and validation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.worldData.generators.terrain.relief.reliefLog import relief_warning
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
    relief_template_registry,
    terrain,
)


class ReliefWorldImportService:

    def __init__(
        self,
        world_service: WorldService,
        library: ReliefTemplateLibraryService,
    ) -> None:
        self._worlds = world_service
        self._library = library

    async def import_outlines_into_world(
        self,
        world_uid: str,
        outlines: list[dict],
    ) -> dict:
        """Upsert bodies to library, add registry pointers, R34 terrain sync."""
        world = await self._worlds.get_by_id(world_uid)
        barrier_keys = {
            e.system_type for e in barrier_templates(world).root
        } if barrier_templates(world).root else set()

        imported_uids: list[str] = []
        for raw in outlines:
            outline = ReliefTemplate.model_validate(raw)
            self._validate_structure_refs(outline, barrier_keys)
            row = await self._library.upsert_outline(outline, source_file="bundle")
            imported_uids.append(row.template_uid)
            await self._ensure_registry_pointer(world_uid, row.template_uid, outline)
            await self._sync_terrain_from_outline(world_uid, outline, row.template_uid)

        return {"imported": len(imported_uids), "uids": imported_uids}

    async def import_library_uid_into_world(
        self,
        world_uid: str,
        template_uid: str,
    ) -> dict:
        row = await self._library.get_by_uid(template_uid)
        outline = ReliefTemplate.model_validate(row.data)
        world = await self._worlds.get_by_id(world_uid)
        barrier_keys = {
            e.system_type for e in barrier_templates(world).root
        } if barrier_templates(world).root else set()
        self._validate_structure_refs(outline, barrier_keys)
        await self._ensure_registry_pointer(world_uid, template_uid, outline)
        await self._sync_terrain_from_outline(world_uid, outline, template_uid)
        return {"imported": 1, "uids": [template_uid]}

    def _validate_structure_refs(
        self,
        outline: ReliefTemplate,
        barrier_keys: set[str],
    ) -> None:
        if not barrier_keys:
            return
        refs: set[str] = set(outline.structure_refs)
        for cond in outline.conditions:
            for case in cond.cases:
                refs.update(case.structure_refs)
                if case.bands:
                    for band in case.bands:
                        refs.update(band.structure_refs)
        unknown = sorted(refs - barrier_keys)
        if unknown:
            raise ReliefValidationError(
                f"structure_refs unknown in barrier_template_registry: {unknown}",
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
