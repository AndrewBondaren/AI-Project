"""Read-only write inspection — library packs TZ §0.3, §1.2, §3.

Caller owns authentication and the read/commit transaction. This component
collects facts only; LibraryWritePolicy is the sole decision boundary.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields, is_dataclass

from pydantic import BaseModel

from app.application.templateLibrary.packs.defaults import is_default_pack_uid
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.templateLibrary.packs.domainAdapters import PackDomainAdapter
from app.application.worldData.worldService import WorldService
from app.application.templateLibrary.packs.packCatalog import PackCatalogRepos
from app.application.templateLibrary.packs.packIdentity import instance_system_name, published_system_name
from app.application.templateLibrary.packs.write.writeContracts import (
    LibraryWriteItem, LibraryWriteRequest, WriteItemSnapshot, WriteObjectKind, WriteSnapshot,
    WriteSourceKind, WriteTarget,
)
from app.application.templateLibrary.packs.write.writeInspectionContracts import (
    InspectedSource, WriteImportSource, WriteInspectionState,
)
from app.application.templateLibrary.packs.write.writeSourceReader import LibraryWriteSourceReader
from app.application.templateLibrary.packs.write.writeStateReader import LibraryWriteStateReader
from app.ids import LibraryKind, library_uid, state_fingerprint
from app.db.models.libraryPack import LibraryPackRow


def _fingerprint_value(value):
    """Project typed read state without treating domain bodies as metadata."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {f.name: _fingerprint_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {key: _fingerprint_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_fingerprint_value(item) for item in value]
    return value


class LibraryWriteInspector:
    """Collect matching targets and retain the inputs needed by a planner."""

    def __init__(self, *, catalog: PackCatalogRepos,
                 adapters: Mapping[LibraryKind, PackDomainAdapter], worlds: WorldService,
                 locations=None):
        if catalog.deps is None:
            raise ValueError("write inspection requires dependency repositories")
        self._catalog, self._worlds = catalog, worlds
        self._sources = LibraryWriteSourceReader(catalog, adapters)
        self._states = LibraryWriteStateReader(catalog, adapters, self._sources,
                                               locations=locations)

    async def inspect(self, request: LibraryWriteRequest, *,
                      imports: Mapping[str, WriteImportSource] | None = None) -> WriteSnapshot:
        imports = deepcopy(dict(imports or {}))
        sources, facts, scopes, scope_issues = {}, [], {}, {}
        selections = {d.item_key: d for d in request.decisions}
        for item in request.items:
            owner = item.owner_world_uid
            if owner not in scopes:
                world = await self._worlds.find_by_id(owner) if owner is not None else None
                errors = ("destination_world_missing",) if owner is not None and world is None else ()
                try:
                    scopes[owner] = await self._states.read(owner, world)
                except (ValueError, LibraryPackValidationError) as exc:
                    scopes[owner] = None
                    errors += (f"invalid_destination_state:{exc}",)
                scope_issues[owner] = errors
            state = scopes[owner]
            destination = await self._destination(item)
            issues = scope_issues[owner]
            source = None
            matches = ()
            try:
                source = await self._sources.read(item, state.world if state else None, imports)
                sources[item.item_key] = source
                matches = await self._matches(item, source)
            except (ValueError, LibraryPackValidationError) as exc:
                issues += (f"invalid_source:{exc}",)
            selected = selections.get(item.item_key)
            copy_name = selected.copy_system_name if selected else None
            free = await self._identity_available(copy_name) if copy_name else False
            facts.append(WriteItemSnapshot(item, destination, matches, issues,
                                           source.pack.owner_world_uid if source else None,
                                           copy_name, free))
        inspection = await self._inspection_state(sources, scopes, facts)
        # Copy key is supplied after preview. Its current availability is
        # checked independently by policy, not included in the original token.
        stable_facts = [{"item": f.item.model_dump(mode="json"),
                         "destination": _fingerprint_value(f.destination),
                         "matches": _fingerprint_value(f.matches), "issues": f.issues}
                        for f in facts]
        token = state_fingerprint({"version": 1, "items": stable_facts,
                                   "state": _fingerprint_value(inspection)})
        return deepcopy(WriteSnapshot(tuple(facts), token, inspection))

    async def _destination(self, item: LibraryWriteItem) -> WriteTarget:
        if item.object_kind is WriteObjectKind.PACK:
            # Scope descriptor only, not a fabricated entity UID.
            return WriteTarget(item.owner_world_uid or "engine", item.owner_world_uid)
        pack = await self._catalog.packs.get_by_uid(item.target_pack_uid)
        if pack is None:
            return WriteTarget(item.target_pack_uid, item.owner_world_uid, writable=False)
        return self._target(pack)

    async def _matches(self, item: LibraryWriteItem, source: InspectedSource) -> tuple[WriteTarget, ...]:
        if item.object_kind is WriteObjectKind.PACK:
            name = item.target_system_name or source.pack.system_name
            if (item.source.kind is WriteSourceKind.CATALOG
                    and not is_default_pack_uid(source.pack.pack_uid)):
                if source.pack.owner_world_uid is None and item.owner_world_uid is not None:
                    name = instance_system_name(item.owner_world_uid, name)
                elif source.pack.owner_world_uid is not None and item.owner_world_uid is None:
                    name = published_system_name(name)
            uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
            candidates = [await self._catalog.packs.get_by_uid(uid),
                          await self._catalog.packs.get_by_system_name(name)]
            if (item.source.kind is WriteSourceKind.CATALOG
                    and source.pack.owner_world_uid is None and item.owner_world_uid is not None):
                candidates.append(await self._catalog.packs.find_instance(item.owner_world_uid, source.pack.pack_uid))
            matches = {p.pack_uid: self._target(p) for p in candidates if p}
            if is_default_pack_uid(uid) and uid not in matches:
                matches[uid] = WriteTarget(uid, None, is_default=True, writable=False)
            return tuple(matches[key] for key in sorted(matches))
        member = source.members[0].member
        rows = await self._catalog.members.list_by_local_uid(
            item.target_pack_uid, item.library_kind.value, member.local_uid)
        exact = await self._catalog.members.get_by_uid(member.template_uid)
        if exact is not None and exact.pack_uid == item.target_pack_uid:
            if exact.library_kind != item.library_kind.value:
                raise LibraryPackValidationError("target_uid_kind_mismatch")
            rows.append(exact)
        pack = await self._catalog.packs.get_by_uid(item.target_pack_uid)
        if pack is None:
            return ()
        return tuple(WriteTarget(uid, pack.owner_world_uid, is_default_pack_uid(pack.pack_uid))
                     for uid in sorted({m.template_uid for m in rows}))

    async def _identity_available(self, name: str) -> bool:
        uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
        return (not is_default_pack_uid(uid)
                and await self._catalog.packs.get_by_uid(uid) is None
                and await self._catalog.packs.get_by_system_name(name) is None)

    async def _inspection_state(self, sources, scopes, facts) -> WriteInspectionState:
        states = tuple(s for _, s in sorted(scopes.items(), key=lambda entry: entry[0] or "") if s is not None)
        packs = {p.pack_uid: p for s in states for p in s.packs}
        members = {m.member.template_uid: m.member for s in states for m in s.members}
        pack_uids = {f.destination.uid for f in facts if f.item.object_kind is WriteObjectKind.MEMBER}
        pack_uids.update(t.uid for f in facts if f.item.object_kind is WriteObjectKind.PACK for t in f.matches)
        ref_uids = {r.template_uid for s in states for r in s.refs}
        for source in sources.values():
            packs[source.pack.pack_uid] = source.pack
            members.update((m.member.template_uid, m.member) for m in source.members)
            pack_uids.update(source.dependencies)
            ref_uids.update(r.template_uid for m in source.members
                            for r in self._sources.references(m))
        ref_uids.update(m.source_template_uid for m in members.values() if m.source_template_uid)
        pack_uids.update(p.source_pack_uid for p in packs.values() if p.source_pack_uid)
        for state in states:
            pack_uids.update(uid for _, deps in state.dependencies for uid in deps)
        for uid in sorted(ref_uids - members.keys()):
            member = await self._catalog.members.get_by_uid(uid)
            if member:
                members[uid] = member
                pack_uids.add(member.pack_uid)
        for uid in sorted(pack_uids - packs.keys()):
            pack = await self._catalog.packs.get_by_uid(uid)
            if pack:
                packs[uid] = pack
        dependency_edges = {}
        pending = set(pack_uids) | set(packs)
        while pending:
            uid = min(pending)
            pending.remove(uid)
            required = tuple(sorted(await self._catalog.deps.required_uids(uid)))
            dependency_edges[uid] = required
            for dep in required:
                if dep not in packs:
                    pack = await self._catalog.packs.get_by_uid(dep)
                    if pack:
                        packs[dep] = pack
                if dep not in dependency_edges:
                    pending.add(dep)
        return WriteInspectionState(tuple(sorted(sources.items())), states,
                                     tuple(packs[uid] for uid in sorted(packs)),
                                     tuple(members[uid] for uid in sorted(members)),
                                     tuple(sorted(dependency_edges.items())),
                                     tuple(sorted(await self._catalog.members.existing_uids(sorted(members)))))

    @staticmethod
    def _target(pack: LibraryPackRow) -> WriteTarget:
        return WriteTarget(pack.pack_uid, pack.owner_world_uid, is_default_pack_uid(pack.pack_uid))
