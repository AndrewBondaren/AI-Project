"""Manifest → catalog rows and atomic insert-missing attach — TZ §3/§4.

FS-imported packs land as engine libraries (``owner_world_uid`` NULL);
no provenance is declared on FS manifests. All writes are fill-missing
(``insert_missing``) — membership never changes an existing owner and a
repeated import is uid-stable/idempotent.
"""

from __future__ import annotations

from app.dataModel.libraryPacks.packManifest import LibraryPackManifest
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.repositories.iLibraryPackDependencyRepository import (
    ILibraryPackDependencyRepository,
)
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository


def pack_row_for(
    manifest: LibraryPackManifest,
    *,
    owner_world_uid: str | None = None,
    source_pack_uid: str | None = None,
) -> LibraryPackRow:
    return LibraryPackRow(
        pack_uid=manifest.pack_uid,
        system_name=manifest.system_name,
        pack_name=manifest.pack_name,
        display_name=manifest.display_name,
        version=manifest.version,
        owner_world_uid=owner_world_uid,
        source_pack_uid=source_pack_uid,
    )


def member_rows_for(
    manifest: LibraryPackManifest,
    *,
    pack_uid: str | None = None,
) -> list[LibraryPackMemberRow]:
    return [
        LibraryPackMemberRow(
            template_uid=member.template_uid,
            pack_uid=pack_uid or manifest.pack_uid,
            library_kind=member.library_kind,
            local_uid=member.local_uid,
            source_template_uid=member.source_template_uid,
        )
        for member in manifest.members
    ]


def dependency_rows_for(
    manifest: LibraryPackManifest,
    *,
    pack_uid: str | None = None,
) -> list[LibraryPackDependencyRow]:
    return [
        LibraryPackDependencyRow(
            pack_uid=pack_uid or manifest.pack_uid,
            required_pack_uid=required,
        )
        for required in manifest.dependencies
    ]


async def attach_pack_catalog(
    manifest: LibraryPackManifest,
    *,
    packs: ILibraryPackRepository,
    members: ILibraryPackMemberRepository,
    deps: ILibraryPackDependencyRepository,
) -> None:
    """Write pack + members + dependencies via insert-missing (never replaces)."""
    await packs.insert_missing([pack_row_for(manifest)])
    await members.insert_missing(member_rows_for(manifest))
    await deps.insert_missing(dependency_rows_for(manifest))
