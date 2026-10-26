"""Read/validate catalog or parsed import sources; never persists (TZ §0.3)."""
from copy import deepcopy
from collections.abc import Mapping

from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.templateLibrary.packs.domainAdapters import PackDomainAdapter
from app.application.templateLibrary.packs.lifecycleContracts import MemberRef
from app.application.templateLibrary.packs.packCatalog import PackCatalogRepos
from app.application.templateLibrary.packs.write.writeContracts import LibraryWriteItem, WriteObjectKind, WriteSourceKind
from app.application.templateLibrary.packs.write.writeInspectionContracts import (
    InspectedMember, InspectedSource, WriteImportMember, WriteImportSource,
)
from app.ids import LibraryKind, UID_PART_SEPARATOR, library_uid
from app.db.models.world import World
from app.db.models.libraryPackMember import LibraryPackMemberRow


class LibraryWriteSourceReader:
    """Normalize one source using existing domain body contracts."""

    def __init__(self, catalog: PackCatalogRepos, adapters: Mapping[LibraryKind, PackDomainAdapter]):
        self._catalog = catalog
        self._adapters = adapters

    async def read(self, item: LibraryWriteItem, world: World | None,
                   imports: Mapping[str, WriteImportSource]) -> InspectedSource:
        if item.source.kind is not WriteSourceKind.CATALOG:
            raw = deepcopy(imports.get(item.source.key))
            if raw is None:
                raise LibraryPackValidationError("import_source_missing")
        else:
            raw = await self._catalog_source(item)
        self._validate_pack(raw)
        if item.object_kind is WriteObjectKind.MEMBER:
            if len(raw.members) != 1 or raw.members[0].member.library_kind != item.library_kind.value:
                raise LibraryPackValidationError("source_member_kind_mismatch")
        prepared = tuple(self.prepare(entry, world)
                         for entry in sorted(raw.members, key=lambda entry: entry.member.template_uid))
        return InspectedSource(raw.pack, prepared, tuple(sorted(set(raw.dependencies))))

    async def _catalog_source(self, item: LibraryWriteItem) -> WriteImportSource:
        if item.object_kind is WriteObjectKind.MEMBER:
            member = await self._catalog.members.get_by_uid(item.source.key)
            if member is None:
                raise LibraryPackValidationError("source_member_missing")
            members = [member]
            pack_uid = member.pack_uid
        else:
            pack_uid = item.source.key
            members = await self._catalog.members.list_by_pack(pack_uid)
        pack = await self._catalog.packs.get_by_uid(pack_uid)
        if pack is None:
            raise LibraryPackValidationError("source_pack_missing")
        entries = tuple([await self.read_member(member) for member in members])
        deps = await self._catalog.deps.required_uids(pack.pack_uid)
        return deepcopy(WriteImportSource(pack, entries, tuple(sorted(deps))))

    async def read_member(self, member: LibraryPackMemberRow) -> WriteImportMember:
        adapter = self._adapters.get(LibraryKind(member.library_kind))
        if adapter is None:
            raise LibraryPackValidationError("source_domain_unavailable")
        found = await adapter.read_body_row(member.template_uid)
        if found is None:
            raise LibraryPackValidationError(f"member_body_missing:{member.template_uid}")
        body, file = found
        return deepcopy(WriteImportMember(member, body, file))

    def prepare(self, entry: WriteImportMember, world: World | None) -> InspectedMember:
        member = entry.member
        adapter = self._adapters.get(LibraryKind(member.library_kind))
        if adapter is None:
            raise LibraryPackValidationError("source_domain_unavailable")
        outline = adapter.prepare_body(deepcopy(entry.body), local_uid=member.local_uid,
                                       template_uid=member.template_uid, world=deepcopy(world))
        body = (outline.model_dump(mode="json") if LibraryKind(member.library_kind) in
                (LibraryKind.PLOT_TEMPLATES, LibraryKind.BUILDING_TEMPLATES,
                 LibraryKind.STRUCTURE_TEMPLATES) else entry.body)
        return InspectedMember(member, body, outline, entry.source_file)

    def references(self, entry: InspectedMember) -> tuple[MemberRef, ...]:
        return self._adapters[LibraryKind(entry.member.library_kind)].body_refs(
            entry.body, entry.member.template_uid)

    @staticmethod
    def _validate_pack(source: WriteImportSource) -> None:
        pack = source.pack
        if (not pack.system_name.strip() or pack.system_name != pack.system_name.strip()
                or library_uid(LibraryKind.LIBRARY_PACKS, pack.system_name) != pack.pack_uid):
            raise LibraryPackValidationError("source_pack_identity_mismatch")
        uids = [entry.member.template_uid for entry in source.members]
        if len(set(uids)) != len(uids):
            raise LibraryPackValidationError("duplicate_source_member_uid")
        for entry in source.members:
            member = entry.member
            if member.pack_uid != pack.pack_uid or not member.template_uid:
                raise LibraryPackValidationError("source_membership_mismatch")
            if not member.local_uid.strip() or UID_PART_SEPARATOR in member.local_uid:
                raise LibraryPackValidationError("invalid_source_local_uid")
            if member.creation_kind not in ("authored", "pack_copy", "member_copy"):
                raise LibraryPackValidationError("invalid_source_creation_kind")
            if (member.creation_kind == "authored") != (member.source_template_uid is None):
                raise LibraryPackValidationError("invalid_source_provenance")
        if (len(set(source.dependencies)) != len(source.dependencies)
                or pack.pack_uid in source.dependencies
                or any(not uid or UID_PART_SEPARATOR in uid for uid in source.dependencies)):
            raise LibraryPackValidationError("invalid_source_dependency")
