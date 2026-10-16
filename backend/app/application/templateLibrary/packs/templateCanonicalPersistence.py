"""Canonical domain specs over shared SQL fill-missing, in the graph caller UOW."""
from dataclasses import dataclass

from app.application.canonicalLibrary import (
    CanonicalAttachPolicy, CanonicalAttachResult, CanonicalContractError,
    CanonicalLibrarySpec, CanonicalScope, CanonicalSnapshot, SqlCanonicalPersistence,
)
from app.application.worldData.libraryPacks.packCatalog import (
    PackCatalogRepos, attach_pack_catalog, pack_row_for,
)
from app.application.worldData.libraryPacks.templateCanonicalSource import CanonicalTemplatePack
from app.db.database import Database


@dataclass(frozen=True)
class TemplateCanonicalContext:
    db: Database
    catalog: PackCatalogRepos
    pack: CanonicalTemplatePack

    def require_uow(self):
        if not self.db.main_conn.owns_unit_of_work:
            raise RuntimeError("canonical graph specs require caller main-connection UOW")


class TemplateCanonicalSource:
    async def load(self, context: TemplateCanonicalContext):
        # The graph facade validated every domain before starting the transaction.
        # Requiring its UOW also keeps canonical lock ordering consistent.
        context.require_uow()
        return CanonicalSnapshot(entries=context.pack.entries)


class TemplateCanonicalPersistence:
    async def insert_missing(self, snapshot, context: TemplateCanonicalContext):
        context.require_uow()
        catalog, pack = context.catalog, context.pack
        expected_pack = pack_row_for(pack.manifest)
        existing_pack = await catalog.packs.get_by_uid(expected_pack.pack_uid)
        if existing_pack is not None and (
            existing_pack.system_name != expected_pack.system_name
            or existing_pack.owner_world_uid is not None or existing_pack.source_pack_uid is not None
        ):
            raise CanonicalContractError("canonical pack identity/ownership conflicts with stored pack")
        present = set()
        for entry in snapshot.entries:
            actual = await catalog.members.get_by_uid(entry.uid)
            if actual is not None:
                if actual != entry.body.member:
                    raise CanonicalContractError(f"canonical membership conflicts: {entry.uid}")
                present.add(entry.uid)
        await attach_pack_catalog(pack.manifest, catalog)
        if not snapshot.entries:
            return CanonicalAttachResult()
        persistence = SqlCanonicalPersistence(model=type(snapshot.entries[0].body.row),
            row_of=lambda entry: entry.body.row)
        bodies = await persistence.insert_missing(snapshot, context.db)
        existing = set(bodies.existing) & present if existing_pack is not None else set()
        return CanonicalAttachResult(
            added=tuple(e.uid for e in snapshot.entries if e.uid not in existing),
            existing=tuple(e.uid for e in snapshot.entries if e.uid in existing))


def template_canonical_spec(pack: CanonicalTemplatePack) -> CanonicalLibrarySpec:
    return CanonicalLibrarySpec(name=pack.kind.value, scope=CanonicalScope.GLOBAL,
        attach_policy=CanonicalAttachPolicy.GLOBAL_FILL_MISSING,
        global_source=TemplateCanonicalSource(), global_persistence=TemplateCanonicalPersistence())
