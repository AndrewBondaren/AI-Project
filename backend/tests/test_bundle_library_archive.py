"""C-5 transport round-trips; no SQL/domain catalog is needed for these tests."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.application.worldData.bundle.archive import BundleArchiveError, read_archive, write_archive
from app.dataModel.worldBundle.bundleManifest import BundleManifest
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchivePack


def pack_fixture(uid="pack-a"):
    manifest = LibraryArchiveManifest.model_validate({
        "pack_uid": uid, "system_name": f"world.instance.{uid}", "pack_name": "same-name",
        "display_name": "Библиотека", "version": "2.0", "source_pack_uid": "source-pack",
        "dependencies": ["external-pack", "pack-b"],
        "defaults": {"structure_templates": "house"},
        "custom_metadata": {"author": "Автор", "flags": [1, 2]},
        "members": [
            {"library_kind": "relief_templates", "local_uid": "hill", "template_uid": f"{uid}-r1",
             "source_template_uid": "source-r1", "creation_kind": "pack_copy",
             "source_file": "old-name/hill.json", "custom_member": {"note": "keep"}},
            {"library_kind": "relief_templates", "local_uid": "hill", "template_uid": f"{uid}-r2",
             "creation_kind": "member_copy"},
            {"library_kind": "structure_templates", "local_uid": "house", "template_uid": f"{uid}-s1"},
        ],
    })
    return LibraryArchivePack(manifest, {
        f"{uid}-r1": {"system_name": "hill", "height": 1, "ref": f"{uid}-s1"},
        f"{uid}-r2": {"system_name": "hill", "height": 2, "ref": "pack-b-r1"},
        f"{uid}-s1": {"system_name": f"{uid}-s1", "refs": [f"{uid}-r1", f"{uid}-r2"]},
    })


def root_manifest(*, kind="world", pack_uid="pack-a"):
    source = {"kind": kind, "exporter": "test", "exported_at": "2026-10-12T00:00:00Z"}
    source.update({"world_uid": "world-a", "world_name": "Мир"} if kind == "world" else {"pack_uid": pack_uid})
    return BundleManifest.model_validate({
        "kind": kind, "format_version": 1, "source": source,
        "sections": {"world": "skeleton/world.json"} if kind == "world" else {},
    })


class BundleLibraryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.wpack"
        self.sections = {"world": {"world_uid": "world-a", "name": "Мир"}}
        self.root = root_manifest()
        self.pack = pack_fixture()

    def write(self, packs=None):
        write_archive(self.sections, self.root, path=self.path,
                      library_packs=[self.pack] if packs is None else packs)

    def entries(self):
        with ZipFile(self.path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def replace_entries(self, entries):
        with ZipFile(self.path, "w") as archive:
            for name, value in entries.items():
                archive.writestr(name, value)

    def mutate_manifests(self, fn, *, one=False):
        entries = self.entries()
        for path in list(entries):
            if path.endswith("/pack.manifest.json"):
                wire = json.loads(entries[path])
                fn(wire)
                entries[path] = json.dumps(wire).encode()
                if one:
                    break
        self.replace_entries(entries)

    def test_world_multidomain_round_trip_preserves_names_uids_refs_and_metadata(self):
        self.write([self.pack, pack_fixture("pack-b")])
        contents = read_archive(self.path)
        self.assertEqual(contents.sections, self.sections)
        self.assertEqual(contents.blobs, {})
        self.assertEqual(contents.library_packs, (self.pack, pack_fixture("pack-b")))
        entries = self.entries()
        for uid in ("pack-a", "pack-b"):
            for domain in ("relief_templates", "structures_templates"):
                self.assertIn(f"library/{domain}/{uid}/pack.manifest.json", entries)
            self.assertIn(f"library/relief_templates/{uid}/{uid}-r1.json", entries)
            self.assertIn(f"library/relief_templates/{uid}/{uid}-r2.json", entries)
        self.assertFalse(any("same-name" in path or "hill.json" in path for path in entries))
        self.assertEqual(entries["library/relief_templates/pack-a/pack.manifest.json"],
                         entries["library/structures_templates/pack-a/pack.manifest.json"])
        self.assertEqual(contents.library_packs[0].manifest.model_dump(exclude_unset=True),
                         self.pack.manifest.model_dump(exclude_unset=True))

    def test_standalone_multidomain_uses_same_uid_layout_without_library_prefix(self):
        root = root_manifest(kind="library_pack")
        write_archive({}, root, path=self.path, library_packs=[self.pack])
        contents = read_archive(self.path)
        self.assertEqual(contents.library_packs, (self.pack,))
        self.assertEqual(contents.sections, {})
        self.assertIn("relief_templates/pack-a/pack-a-r1.json", self.entries())
        self.assertFalse(any(path.startswith(("library/", "skeleton/", "pack/")) for path in self.entries()))

    def test_standalone_source_mismatch_or_multiple_packs_rejected(self):
        for packs in ([], [pack_fixture("pack-b")], [self.pack, pack_fixture("pack-b")]):
            with self.assertRaisesRegex(BundleArchiveError, "source pack UID"):
                write_archive({}, root_manifest(kind="library_pack"), path=self.path, library_packs=packs)

    def test_standalone_rejects_baked_pack_and_arbitrary_subtrees(self):
        root = root_manifest(kind="library_pack")
        with self.assertRaisesRegex(BundleArchiveError, "does not permit raw subtrees"):
            write_archive({}, root, {"pack/manifest.json": b"{}"},
                          path=self.path, library_packs=[self.pack])
        write_archive({}, root, path=self.path, library_packs=[self.pack])
        entries = self.entries()
        entries["pack/manifest.json"] = b"{}"
        self.replace_entries(entries)
        with self.assertRaisesRegex(BundleArchiveError, "Unknown archive files"):
            read_archive(self.path)
        with self.assertRaisesRegex(BundleArchiveError, "does not permit raw subtrees"):
            read_archive(self.path, blob_paths=["pack/manifest.json"])

    def test_standalone_reader_rejects_source_mismatch(self):
        write_archive({}, root_manifest(kind="library_pack"), path=self.path, library_packs=[self.pack])
        entries = self.entries()
        root = json.loads(entries["bundle.manifest.json"])
        root["source"]["pack_uid"] = "other"
        entries["bundle.manifest.json"] = json.dumps(root).encode()
        self.replace_entries(entries)
        with self.assertRaisesRegex(BundleArchiveError, "source pack UID"):
            read_archive(self.path)

    def test_reproducible_bytes_and_input_unchanged(self):
        before = copy.deepcopy(self.pack)
        self.write([self.pack, pack_fixture("pack-b")])
        original = self.path.read_bytes()
        reordered = LibraryArchivePack(self.pack.manifest, dict(reversed(list(self.pack.bodies.items()))))
        self.write([pack_fixture("pack-b"), reordered])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pack, before)
        with ZipFile(self.path) as archive:
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            self.assertTrue(all(info.compress_type == ZIP_DEFLATED for info in archive.infolist()))

    def test_missing_body_or_domain_manifest_rejected(self):
        self.write()
        original = self.entries()
        for missing in ("library/relief_templates/pack-a/pack-a-r1.json",
                        "library/structures_templates/pack-a/pack.manifest.json"):
            with self.subTest(missing=missing):
                self.replace_entries({k: v for k, v in original.items() if k != missing})
                with self.assertRaisesRegex(BundleArchiveError, "Missing archive files"):
                    read_archive(self.path)

    def test_unknown_files_roots_and_lone_bodies_rejected_before_section_json(self):
        self.write()
        original = self.entries()
        for extra in ("library/relief_templates/lone.json",
                      "library/relief_templates/pack-a/undeclared.json",
                      "library/unknown/pack-a/pack.manifest.json",
                      "library/relief_templates/same-name/hill.json"):
            entries = dict(original)
            entries["skeleton/world.json"] = b"invalid section"
            entries[extra] = b"{}"
            self.replace_entries(entries)
            with self.assertRaisesRegex(BundleArchiveError, "Unknown archive files"):
                read_archive(self.path)

    def test_folder_uid_must_match_manifest(self):
        self.write()
        entries = {path.replace("/pack-a/", "/wrong/"): value for path, value in self.entries().items()}
        self.replace_entries(entries)
        with self.assertRaisesRegex(BundleArchiveError, "folder must match pack UID"):
            read_archive(self.path)

    def test_conflicting_copies_of_manifest_rejected(self):
        self.write()
        self.mutate_manifests(lambda manifest: manifest.update(version="changed"), one=True)
        with self.assertRaisesRegex(BundleArchiveError, "Conflicting manifests"):
            read_archive(self.path)

    def test_duplicate_member_uids_rejected_within_and_between_packs(self):
        wire = self.pack.manifest.model_dump()
        wire["members"].append(wire["members"][0])
        bad = LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), self.pack.bodies)
        for packs in ([bad], [self.pack, self.pack]):
            with self.assertRaisesRegex(BundleArchiveError, "Duplicate library"):
                self.write(packs)
        other = pack_fixture("pack-b")
        wire = other.manifest.model_dump()
        wire["members"][0]["template_uid"] = "pack-a-r1"
        other = LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), other.bodies)
        with self.assertRaisesRegex(BundleArchiveError, "Duplicate library member"):
            self.write([self.pack, other])

    def test_reader_duplicate_member_uid_rejected(self):
        self.write()
        self.mutate_manifests(lambda wire: wire["members"].append(wire["members"][0]))
        with self.assertRaisesRegex(BundleArchiveError, "Duplicate library member"):
            read_archive(self.path)

    def test_unsafe_uid_segments_rejected(self):
        for uid in ("../escape", "a/b", "C:drive", "CON", "trailing.", "x\\y", "bad?uid"):
            wire = self.pack.manifest.model_dump()
            wire["members"][0]["template_uid"] = uid
            with self.subTest(uid=uid), self.assertRaises(BundleArchiveError):
                self.write([LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), self.pack.bodies)])

    def test_body_cannot_use_manifest_filename(self):
        wire = self.pack.manifest.model_dump()
        wire["members"][0]["template_uid"] = "pack.manifest"
        with self.assertRaisesRegex(BundleArchiveError, "collides"):
            self.write([LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), self.pack.bodies)])

    def test_source_file_is_preserved_as_diagnostic_and_never_used_as_path(self):
        wire = self.pack.manifest.model_dump(exclude_unset=True)
        wire["members"][0]["source_file"] = "../../outside.json"
        pack = LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), self.pack.bodies)
        self.write([pack])
        self.assertEqual(read_archive(self.path).library_packs, (pack,))
        self.assertFalse(any("outside" in path for path in self.entries()))

    def test_unknown_kind_and_nonobject_body_rejected(self):
        self.write()
        self.mutate_manifests(lambda wire: wire["members"][0].update(library_kind="unknown"))
        with self.assertRaisesRegex(BundleArchiveError, "Unknown library kind"):
            read_archive(self.path)
        self.write()
        entries = self.entries()
        entries["library/relief_templates/pack-a/pack-a-r1.json"] = b"[]"
        self.replace_entries(entries)
        with self.assertRaisesRegex(BundleArchiveError, "body must be an object"):
            read_archive(self.path)

    def test_missing_and_extra_bodies_rejected_before_writer_replaces_file(self):
        self.path.write_bytes(b"original")
        for bodies in ({}, {**self.pack.bodies, "extra": {}}):
            with self.assertRaisesRegex(BundleArchiveError, "bodies must match"):
                self.write([LibraryArchivePack(self.pack.manifest, bodies)])
            self.assertEqual(self.path.read_bytes(), b"original")

    def test_empty_pack_rejected_without_guessing_domain(self):
        wire = self.pack.manifest.model_dump()
        wire["members"] = []
        with self.assertRaisesRegex(BundleArchiveError, "no domain members"):
            self.write([LibraryArchivePack(LibraryArchiveManifest.model_validate(wire), {})])

    def test_flat_body_duplication_rejected_on_writer_and_reader(self):
        sections = {**self.sections, "relief_templates": [{"template_uid": "pack-a-r1"}]}
        wire = self.root.model_dump()
        wire["sections"]["relief_templates"] = "skeleton/relief_templates.json"
        root = BundleManifest.model_validate(wire)
        with self.assertRaisesRegex(BundleArchiveError, "duplicated in flat section"):
            write_archive(sections, root, path=self.path, library_packs=[self.pack])
        self.write()
        entries = self.entries()
        entries["bundle.manifest.json"] = root.model_dump_json().encode()
        entries["skeleton/relief_templates.json"] = json.dumps(sections["relief_templates"]).encode()
        self.replace_entries(entries)
        with self.assertRaisesRegex(BundleArchiveError, "duplicated in flat section"):
            read_archive(self.path)

    def test_raw_blobs_cannot_overwrite_typed_library_files(self):
        path = "library/relief_templates/pack-a/pack-a-r1.json"
        with self.assertRaisesRegex(BundleArchiveError, "overlaps raw blob"):
            write_archive(self.sections, self.root, {path: b"{}"}, path=self.path, library_packs=[self.pack])
