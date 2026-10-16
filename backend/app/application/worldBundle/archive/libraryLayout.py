"""UID-only library layout; transport checks without repositories or remapping."""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.application.worldData.bundle.archive.errors import BundleArchiveError
from app.application.worldData.bundle.archive.validation import decode_json, encode_json, validate_path
from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleManifest, BundleLibraryPackSource
from app.dataModel.worldBundle.bundleSections import BundleArchiveLayout
from app.dataModel.worldBundle.libraryArchive import (
    LIBRARY_DOMAIN_ROOTS, PACK_MANIFEST_FILE,
    LibraryArchiveManifest, LibraryArchivePack,
)


@dataclass(frozen=True)
class LibraryLayout:
    packs: Mapping[str, LibraryArchiveManifest]
    manifest_paths: Mapping[str, str]  # path → pack UID
    body_paths: Mapping[str, tuple[str, str]]  # path → (pack UID, member UID)

    @property
    def paths(self) -> set[str]:
        return set(self.manifest_paths) | set(self.body_paths)


def _uid_segment(uid: str) -> str:
    validate_path(uid)
    if ("/" in uid or any(char in uid for char in '<>"|?*')
            or uid.endswith((".", " "))
            or uid.split(".", 1)[0].upper() in {
                "CON", "PRN", "AUX", "NUL",
                *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
            }):
        raise BundleArchiveError(f"Invalid UID path segment: {uid!r}")
    return uid


def _prefix(manifest: BundleManifest) -> str:
    return BundleArchiveLayout.LIBRARY_PREFIX if manifest.kind == BundleKind.WORLD else ""


def _parse_manifest(raw: Any) -> LibraryArchiveManifest:
    try:
        return LibraryArchiveManifest.model_validate(raw)
    except ValidationError as exc:
        raise BundleArchiveError(f"Invalid library manifest: {exc}") from exc


def build_library_layout(
    manifests: Sequence[LibraryArchiveManifest], root: BundleManifest,
) -> LibraryLayout:
    packs: dict[str, LibraryArchiveManifest] = {}
    manifests_by_path: dict[str, str] = {}
    bodies_by_path: dict[str, tuple[str, str]] = {}
    member_uids: set[str] = set()
    prefix = _prefix(root)
    for value in manifests:
        # Frozen models contain mutable collections; validate again at I/O.
        pack = _parse_manifest(value.model_dump(mode="python", exclude_unset=True))
        uid = _uid_segment(pack.pack_uid)
        if uid in packs:
            raise BundleArchiveError(f"Duplicate library pack UID: {uid!r}")
        if not pack.members:
            raise BundleArchiveError(f"Library pack {uid!r} declares no domain members")
        packs[uid] = pack
        for member in pack.members:
            domain = LIBRARY_DOMAIN_ROOTS.get(member.library_kind)
            if domain is None:
                raise BundleArchiveError(f"Unknown library kind: {member.library_kind!r}")
            member_uid = _uid_segment(member.template_uid)
            if member_uid in member_uids:
                raise BundleArchiveError(f"Duplicate library member UID: {member_uid!r}")
            member_uids.add(member_uid)
            directory = f"{prefix}{domain}/{uid}/"
            manifests_by_path[directory + PACK_MANIFEST_FILE] = uid
            bodies_by_path[directory + member_uid + ".json"] = (uid, member_uid)
    if root.kind == BundleKind.LIBRARY_PACK:
        source = root.source
        if not isinstance(source, BundleLibraryPackSource) or set(packs) != {source.pack_uid}:
            raise BundleArchiveError("Library archive must carry exactly its source pack UID")
    if set(manifests_by_path) & set(bodies_by_path):
        raise BundleArchiveError("Library body path collides with pack manifest")
    return LibraryLayout(packs, manifests_by_path, bodies_by_path)


def discover_library_layout(
    files: Collection[str], root: BundleManifest, read: Callable[[str], bytes],
) -> LibraryLayout:
    """Only canonical manifest candidates can declare more expected files.

    A matching prefix is never an allowlist. The caller compares the complete
    inventory with the paths derived from the manifests before reading bodies.
    """
    prefix = _prefix(root)
    packs: dict[str, LibraryArchiveManifest] = {}
    for path in sorted(files):
        if prefix and not path.startswith(prefix):
            continue
        relative = path[len(prefix):]
        parts = relative.split("/")
        if (len(parts) != 3 or parts[0] not in LIBRARY_DOMAIN_ROOTS.values()
                or parts[2] != PACK_MANIFEST_FILE):
            continue
        pack = _parse_manifest(decode_json(read(path), path))
        if parts[1] != _uid_segment(pack.pack_uid):
            raise BundleArchiveError(f"Library folder must match pack UID: {path!r}")
        prior = packs.get(pack.pack_uid)
        if prior is not None and prior.model_dump(exclude_unset=True) != pack.model_dump(exclude_unset=True):
            raise BundleArchiveError(f"Conflicting manifests for pack {pack.pack_uid!r}")
        packs[pack.pack_uid] = pack
    return build_library_layout(list(packs.values()), root)


def read_library_packs(layout: LibraryLayout, read: Callable[[str], bytes]) -> tuple[LibraryArchivePack, ...]:
    bodies: dict[str, dict[str, dict]] = {uid: {} for uid in layout.packs}
    for path, (pack_uid, member_uid) in sorted(layout.body_paths.items()):
        body = decode_json(read(path), path)
        if not isinstance(body, dict):
            raise BundleArchiveError(f"Library body must be an object: {path!r}")
        bodies[pack_uid][member_uid] = body
    return tuple(LibraryArchivePack(layout.packs[uid], bodies[uid]) for uid in sorted(layout.packs))


def write_library_entries(
    packs: Sequence[LibraryArchivePack], root: BundleManifest,
) -> tuple[dict[str, bytes], LibraryLayout]:
    layout = build_library_layout([pack.manifest for pack in packs], root)
    by_uid = {pack.manifest.pack_uid: pack for pack in packs}
    entries = {
        path: encode_json(layout.packs[uid].model_dump(mode="json", exclude_unset=True), path)
        for path, uid in layout.manifest_paths.items()
    }
    for uid, pack in by_uid.items():
        expected = {member.template_uid for member in layout.packs[uid].members}
        if set(pack.bodies) != expected:
            raise BundleArchiveError(f"Library bodies must match manifest members: {uid!r}")
    for path, (pack_uid, member_uid) in layout.body_paths.items():
        body = by_uid[pack_uid].bodies[member_uid]
        if not isinstance(body, dict):
            raise BundleArchiveError(f"Library body must be an object: {path!r}")
        entries[path] = encode_json(body, path)
    return entries, layout


def reject_flat_duplicates(sections: Mapping[str, Any], layout: LibraryLayout) -> None:
    for pack in layout.packs.values():
        for member in pack.members:
            rows = sections.get(member.library_kind, [])
            if isinstance(rows, list) and any(
                isinstance(row, dict) and row.get("template_uid") == member.template_uid for row in rows
            ):
                raise BundleArchiveError(f"Packed library body duplicated in flat section: {member.template_uid!r}")
