"""B2 application seam: facts + pure B1 plan -> common writer inputs.

``plan_legacy_world_migration`` performs no SQL; this module alone loads the
catalog snapshot the plan consumes, mirrors the write planner's copy identity
for bundle archive sources, and translates projected pack routes back into
``WriteImportSource`` / ``LibraryWriteItem`` pairs the caller merges into the
shared world-import write request (tz_template_library_packs §4.1, plan 5b §B2).
"""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.libraryPacks.domainAdapters.contract import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.legacyDomainContracts import (
    LEGACY_PLOT_FIELDS,
    LegacyDomainShape,
)
from app.application.worldData.libraryPacks.legacyPack import legacy_member_uid
from app.application.worldData.libraryPacks.legacyWorldBodies import target_kind
from app.application.worldData.libraryPacks.legacyWorldContracts import (
    LegacyPackRoute,
    LegacyWorldFacts,
    LegacyWorldMigrationPlan,
)
from app.application.worldData.libraryPacks.legacyWorldInput import LegacyWorldInput
from app.application.worldData.libraryPacks.legacyWorldPlan import plan_legacy_world_migration
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.libraryPacks.uidMap import (
    RELIEF_SMOKE_003_FORMER_UIDS,
    STRUCTURE_MEMBER_RENAMES,
    former_template_uid,
    mapped_template_uid,
)
from app.application.worldData.libraryPacks.writeContracts import (
    LibraryWriteItem,
    WriteSource,
)
from app.application.worldData.libraryPacks.writeInspectionContracts import (
    WriteImportMember,
    WriteImportSource,
)
from app.ids import LibraryKind, library_uid, remapped_library_uid

# Resolution-uncertain codes: SQL catalog members may still supply what the
# wire-only validate facts lack, so these surface at import, not preflight.
_WIRE_DEFERRED = frozenset({"LEGACY_REF_UNKNOWN", "LEGACY_REF_UNAVAILABLE"})


def former_uid_aliases() -> dict[str, str]:
    """Engine-level identity of pre-migration uids the explicit map knows."""
    return {
        old: new
        for old in (*STRUCTURE_MEMBER_RENAMES, *RELIEF_SMOKE_003_FORMER_UIDS)
        if (new := mapped_template_uid(old)) is not None
    }


def project_bundle_sources(sources, items):
    """Mirror the write planner's import identity on archive sources.

    Carrying (target == source) keeps member uids; an owner change mirrors
    ``project_pack``/``PackWritePlanner`` INSTANCE projection: instance system
    name, remapped member uids, ``pack_copy`` provenance. Returns
    ``(projections, alias)`` where ``alias`` maps each source member uid to
    its projected destination uid.
    """
    named = [
        (item, sources[item.source.key], item.target_system_name or sources[item.source.key].pack.system_name)
        for item in items
    ]
    pack_map = {
        item.source.key: library_uid(LibraryKind.LIBRARY_PACKS, name)
        for item, _, name in named
    }
    projections, aliases = [], {}
    for item, source, name in named:
        uid = pack_map[item.source.key]
        if uid == source.pack.pack_uid:
            projections.append(WriteImportSource(deepcopy(source.pack), source.members, source.dependencies))
            continue
        members = []
        for entry in source.members:
            member = replace(
                entry.member,
                template_uid=remapped_library_uid(
                    LibraryKind(entry.member.library_kind),
                    target_pack_uid=uid,
                    source_template_uid=entry.member.template_uid,
                ),
                pack_uid=uid,
                source_template_uid=entry.member.template_uid,
                creation_kind="pack_copy",
            )
            aliases[entry.member.template_uid] = member.template_uid
            members.append(WriteImportMember(member, entry.body, entry.source_file))
        dependencies = tuple(sorted({pack_map.get(dep, dep) for dep in source.dependencies} - {uid}))
        projections.append(WriteImportSource(
            replace(source.pack, pack_uid=uid, system_name=name,
                    owner_world_uid=item.owner_world_uid, source_pack_uid=source.pack.pack_uid),
            tuple(members), dependencies))
    return projections, aliases


class LegacyWorldMigration:
    """Loads facts, runs the pure plan, and emits writer items for B2 routes."""

    def __init__(
        self,
        *,
        catalog: PackCatalogRepos,
        adapters: Mapping[LibraryKind, PackDomainAdapter],
        archives,
    ) -> None:
        self._catalog, self._adapters, self._archives = catalog, adapters, archives

    @staticmethod
    def has_content(legacy: LegacyWorldInput | None) -> bool:
        return bool(legacy and (legacy.pointers or legacy.bodies))

    @staticmethod
    def world_fields(plan: LegacyWorldMigrationPlan) -> dict:
        """Projected world-row fields: migrated pins and remapped pick policy."""
        world = plan.projected_world
        fields = {"library_pins": world.get("library_pins") or []}
        if "relief_pick_policy" in world:
            fields["relief_pick_policy"] = world["relief_pick_policy"]
        return fields

    @staticmethod
    def writer_inputs(plan: LegacyWorldMigrationPlan, *, target_owner: str):
        """Pack projections the writer must persist; REUSE needs no write."""
        imports, items = {}, []
        for projection in plan.packs:
            if projection.route is LegacyPackRoute.REUSE:
                continue
            key = projection.target_pack.pack_uid
            imports[key] = WriteImportSource(
                projection.target_pack, projection.members, projection.dependencies)
            items.append(LibraryWriteItem(
                item_key=key, object_kind="pack",
                source=WriteSource(kind="import", key=key),
                owner_world_uid=target_owner))
        return imports, tuple(items)

    def plan_wire(self, legacy: LegacyWorldInput, packs) -> tuple[FieldPathError, ...]:
        """Validate-only plan over wire facts; SQL-dependent issues defer to import."""
        uid = legacy.raw_world["world_uid"]
        imports, items = self._archives.sources(packs, source_owner=uid, target_owner=uid)
        projected, bundle_aliases = project_bundle_sources(imports, items)
        aliases = {**former_uid_aliases(), **self._member_aliases(legacy, uid, uid), **bundle_aliases}
        projected = tuple(projected)
        facts = LegacyWorldFacts(projected, tuple(sorted(aliases.items())),
                                 tuple(sorted(self._shapes(projected))))
        plan = plan_legacy_world_migration(legacy, facts)
        return tuple(issue for issue in plan.issues if issue.code not in _WIRE_DEFERRED)

    async def plan(
        self,
        legacy: LegacyWorldInput,
        *,
        source_owner: str,
        target_owner: str,
        bundle_sources=(),
        bundle_items=(),
    ) -> LegacyWorldMigrationPlan:
        """Full plan: SQL facts + wire projections + composed uid aliases."""
        projected, bundle_aliases = project_bundle_sources(bundle_sources, bundle_items)
        aliases = {**former_uid_aliases(),
                   **self._member_aliases(legacy, source_owner, target_owner),
                   **bundle_aliases}
        facts = await self._collect_facts(legacy, target_owner, projected, aliases)
        original = replace(legacy, raw_world={**legacy.raw_world, "world_uid": target_owner})
        return plan_legacy_world_migration(original, facts).require_valid()

    @staticmethod
    def _member_aliases(legacy: LegacyWorldInput, source_owner: str, target_owner: str):
        """Source-era identities of authored bodies -> the target member.

        A body with no declared ``template_uid`` still had a deterministic
        identity in the source world (its legacy member uid) and possibly a
        former-table uid. Both must resolve to the member the plan authors so
        pins, policy refs and in-body refs follow the world's own copy.
        """
        aliases = {}
        for body in legacy.bodies:
            if body.source_uid is not None or not body.local_uid:
                continue
            kind = target_kind(body.source_kind, body.shape)
            target = legacy_member_uid(kind, body.local_uid, world_uid=target_owner)
            aliases[legacy_member_uid(kind, body.local_uid, world_uid=source_owner)] = target
            former = former_template_uid(kind, body.local_uid)
            if former is not None:
                aliases[former] = target
        return aliases

    @staticmethod
    def _shapes(sources) -> set[tuple[str, LegacyDomainShape]]:
        return {
            (entry.member.template_uid, LegacyDomainShape.PLOT)
            for source in sources for entry in source.members
            if entry.member.library_kind == LibraryKind.BUILDING_TEMPLATES.value
            and isinstance(entry.body, dict)
            and any(key in entry.body for key in LEGACY_PLOT_FIELDS)
        }

    async def _collect_facts(
        self,
        legacy: LegacyWorldInput,
        target_owner: str,
        projected,
        aliases,
    ) -> LegacyWorldFacts:
        """Complete snapshot: engine + target-owned + pointed/candidate packs."""
        packs_repo, members_repo, deps_repo = (
            self._catalog.packs, self._catalog.members, self._catalog.deps)
        pack_uids = {pack.pack_uid for pack in await packs_repo.list_engine()}
        pack_uids.update(pack.pack_uid for pack in await packs_repo.list_world_owned(target_owner))
        known = {e.member.template_uid for source in projected for e in source.members}
        candidates = {pointer.template_uid for pointer in legacy.pointers}
        candidates.update(body.source_uid for body in legacy.bodies if body.source_uid)
        for uid in sorted({aliases.get(uid, uid) for uid in candidates} - known):
            member = await members_repo.get_by_uid(uid)
            if member is not None:
                pack_uids.add(member.pack_uid)
        sources = {source.pack.pack_uid: source for source in projected}
        for uid in sorted(pack_uids - sources.keys()):
            pack = await packs_repo.get_by_uid(uid)
            if pack is None:
                continue
            entries = []
            members = sorted(await members_repo.list_by_pack(uid), key=lambda m: m.template_uid)
            for member in members:
                adapter = self._adapters.get(LibraryKind(member.library_kind))
                if adapter is None:
                    raise LibraryPackValidationError(
                        f"source_domain_unavailable: {member.library_kind}")
                found = await adapter.read_body_row(member.template_uid)
                if found is None:
                    raise LibraryPackValidationError(
                        f"catalog member body is missing: {member.template_uid}")
                entries.append(WriteImportMember(member, found[0], found[1]))
            dependencies = () if deps_repo is None else tuple(sorted(await deps_repo.required_uids(uid)))
            sources[uid] = WriteImportSource(pack, tuple(entries), dependencies)
        ordered = tuple(sources[uid] for uid in sorted(sources))
        return LegacyWorldFacts(ordered, tuple(sorted(aliases.items())),
                                tuple(sorted(self._shapes(ordered))))
