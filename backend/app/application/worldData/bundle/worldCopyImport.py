"""Atomic world → common library writer → entities import (TZ §4.1/4.2)."""
from dataclasses import replace

from app.application.importResult import ImportResult
from app.application.worldData.bundle.copyTokens import WorldCopyTokens
from app.application.worldData.bundle.worldLibraries import import_libraries
from app.application.worldData.bundleRemapService import build_bundle_uid_map, remap_bundle
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError, LibraryPackPolicyRequiredError, require_no_policy,
)
from app.application.worldData.libraryPacks.writeResults import PolicyRequired
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.ids import state_fingerprint


class ImportFailed(Exception):
    pass


class WorldCopyImport:
    def __init__(self, db, worlds, handlers, archives):
        self._db, self._worlds, self._handlers, self._archives = db, worlds, handlers, archives
        self._tokens = WorldCopyTokens()

    async def run(self, data, *, level, decisions=(), preview_token=None):
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
                world_handler = next(h for h in self._handlers if h.key == BundleSection.WORLD)
                results["world"] = await world_handler.import_section(uid, copied["world"])
                if results["world"].failed:
                    raise ImportFailed()
                packs, consumed = import_libraries(data) if self._archives else ((), set())
                library_token = ("stale" if stale else continuation["library_token"] if continuation else None)
                if packs:
                    plan = require_no_policy(await self._archives.prepare_world(packs,
                        source_owner=data["world"]["world_uid"], target_owner=uid,
                        decisions=decisions, preview_token=library_token))
                    await self._archives.apply(plan)
                    if BundleSection.LIBRARY_PACKS in data:
                        count = len(data[BundleSection.LIBRARY_PACKS])
                        results[BundleSection.LIBRARY_PACKS] = ImportResult(count, count, 0)
                elif preview_token or decisions:
                    # Continuations cannot silently lose their entire library batch.
                    raise LibraryPackPolicyRequiredError(PolicyRequired("", (), (), stale=True))
                for key in consumed:
                    count = len(data[key])
                    results[key] = ImportResult(count, count, 0)
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
