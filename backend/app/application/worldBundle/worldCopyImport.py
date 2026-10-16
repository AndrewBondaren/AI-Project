"""Atomic world → common library writer → entities import (TZ §4.1/4.2)."""
from dataclasses import replace

from app.application.imports.result import ImportResult
from app.application.worldBundle.copyTokens import WorldCopyTokens
from app.application.worldBundle.worldLibraries import import_libraries
from app.application.worldBundle.bundleRemapService import build_bundle_uid_map, remap_bundle
from app.application.templateLibrary.packs.domainAdapters.remapRefs import (
    remap_locations_section,
)
from app.application.templateLibrary.packs.errors import (
    LibraryPackConflictError, LibraryPackPolicyRequiredError, require_no_policy,
)
from app.application.templateLibrary.packs.write.writeResults import PolicyRequired
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.ids import state_fingerprint


class ImportFailed(Exception):
    pass


class WorldCopyImport:
    def __init__(self, db, worlds, handlers, archives, migration=None):
        self._db, self._worlds, self._handlers, self._archives = db, worlds, handlers, archives
        self._migration = migration
        self._tokens = WorldCopyTokens()

    async def run(self, data, *, level, decisions=(), preview_token=None, legacy=None):
        fingerprint = state_fingerprint({"source": data, "level": level})
        continuation = self._tokens.decode(preview_token) if preview_token else None
        stale = continuation is not None and continuation["context"]["source_hash"] != fingerprint
        context = continuation["context"] if continuation and not stale else None
        results = {}
        try:
            async with self._db.transaction():
                if context is None:
                    context = {"source_hash": fingerprint, "uid_map": build_bundle_uid_map(data),
                        "version": await self._worlds.next_version_number(data["world"].get("name", "")),
                        "created_at": self._worlds.prepare_import(data["world"]).created_at}
                copied = remap_bundle(data, context["version"], self._worlds.strip_version_suffix,
                                      uid_map=context["uid_map"])
                copied["world"]["created_at"] = context["created_at"]
                uid = copied["world"]["world_uid"]
                if await self._worlds.find_by_id(uid) is not None:
                    raise LibraryPackConflictError("world copy identity occupied; start a fresh import")
                packs, consumed, imports, items = (), set(), {}, ()
                member_map: dict[str, str] = {}
                if self._archives is not None:
                    migration = (self._migration if self._migration is not None
                                 and self._migration.has_content(legacy) else None)
                    source_owner = data[BundleSection.WORLD]["world_uid"]
                    packs, consumed = import_libraries(data, legacy_migration=migration is not None)
                    if packs:
                        imports, items = self._archives.sources(packs,
                            source_owner=source_owner, target_owner=uid)
                    if migration is not None:
                        # Pure B1 plan over the SQL/wire snapshot; projected
                        # packs and pins join the same writer request (B2).
                        migration_plan = await migration.plan(legacy,
                            source_owner=source_owner, target_owner=uid,
                            bundle_sources=imports, bundle_items=items)
                        member_map.update(dict(migration_plan.uid_map))
                        projected, migration_items = migration.writer_inputs(
                            migration_plan, target_owner=uid)
                        imports = {**imports, **projected}
                        items = (*items, *migration_items)
                        copied["world"].update(migration.world_fields(migration_plan))
                world_handler = next(h for h in self._handlers if h.key == BundleSection.WORLD)
                results["world"] = await world_handler.import_section(uid, copied["world"])
                if results["world"].failed:
                    raise ImportFailed()
                library_token = ("stale" if stale else continuation["library_token"] if continuation else None)
                if items:
                    outcome = require_no_policy(await self._archives.prepare_items(imports, items,
                        decisions=decisions, preview_token=library_token))
                    await self._archives.apply(outcome)
                    member_map.update({src: dst for item in outcome.items
                                       for src, dst in item.uid_map})
                elif preview_token or decisions:
                    # Continuations cannot silently lose their entire library batch.
                    raise LibraryPackPolicyRequiredError(PolicyRequired("", (), (), stale=True))
                if packs:
                    count = len(data[BundleSection.LIBRARY_PACKS])
                    results[BundleSection.LIBRARY_PACKS] = ImportResult(count, count, 0)
                for key in consumed:
                    count = len(data[key])
                    results[key] = ImportResult(count, count, 0)
                # B4: persisted member refs follow the composed member map —
                # entity uid remap above never touches template fields.
                if copied.get(BundleSection.LOCATIONS):
                    copied[BundleSection.LOCATIONS] = remap_locations_section(
                        copied[BundleSection.LOCATIONS], member_map, imports)
                for handler in self._handlers:
                    if handler.key == "world" or handler.key in consumed or handler.key not in copied:
                        continue
                    results[handler.key] = require_no_policy(await handler.import_section(uid, copied[handler.key]))
                if any(result.failed for result in results.values()):
                    raise ImportFailed()
        except LibraryPackPolicyRequiredError as exc:
            outcome = replace(exc.outcome, preview_token=self._tokens.encode(context, exc.outcome.preview_token))
            raise LibraryPackPolicyRequiredError(outcome) from exc
        except ImportFailed:
            return results, True
        return results, False
