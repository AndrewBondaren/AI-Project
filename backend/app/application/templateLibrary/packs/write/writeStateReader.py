"""Read scope/usage facts for preview and retention; no policy (packs TZ §1.2)."""
from collections.abc import Mapping

from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.libraryPacks.writeSourceReader import LibraryWriteSourceReader
from app.db.models.world import World
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.defaults import default_pack_uids
from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot
from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    named_location_template_refs,
)
from app.application.worldData.libraryPacks.referenceResolver import collect_refs, pin_index
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteScopeState


class LibraryWriteStateReader:
    """Load explicit owner/default pack sets and their consumers."""

    def __init__(self, catalog: PackCatalogRepos, adapters: Mapping[LibraryKind, PackDomainAdapter],
                 sources: LibraryWriteSourceReader, *, locations=None):
        self._catalog, self._adapters, self._sources = catalog, adapters, sources
        self._locations = locations

    async def read(self, owner_world_uid: str | None, world: World | None) -> WriteScopeState:
        owned = (await self._catalog.packs.list_engine() if owner_world_uid is None
                 else await self._catalog.packs.list_world_owned(owner_world_uid))
        packs = {p.pack_uid: p for p in owned}
        for uid in sorted(default_pack_uids() - packs.keys()):
            pack = await self._catalog.packs.get_by_uid(uid)
            if pack is not None:
                packs[uid] = pack
        rows = await self._catalog.members.list_by_packs(sorted(packs))
        members = tuple([self._sources.prepare(await self._sources.read_member(m), world)
                         for m in sorted(rows, key=lambda m: m.template_uid)])
        catalog = CatalogSnapshot({m.member.template_uid: m.member for m in members},
                                  {m.member.template_uid: m.body for m in members},
                                  {m.member.template_uid: m.source_file for m in members})
        dependencies = tuple([(uid, tuple(sorted(await self._catalog.deps.required_uids(uid))))
                              for uid in sorted(packs)])
        refs = tuple(sorted(set(collect_refs(self._adapters, catalog, world)),
                            key=lambda r: (r.consumer, r.path, r.library_kind, r.template_uid)))
        location_refs: tuple = ()
        if self._locations is not None and world is not None:
            location_refs = named_location_template_refs(
                await self._locations.get_by_world(world.world_uid), catalog.members)
        pins = tuple(sorted(pin_index(world, catalog.members).items()))
        return WriteScopeState(owner_world_uid, world, tuple(packs[uid] for uid in sorted(packs)),
                               members, dependencies, refs, pins, location_refs=location_refs)
