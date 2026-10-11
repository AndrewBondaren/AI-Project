"""Archive codec round-trip, deterministic output and hostile-input checks."""

import json
import stat
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from app.application.worldData.bundle.archive import (
    BundleArchiveError,
    read_archive,
    write_archive,
)
from app.dataModel.worldBundle import BundleArchiveLayout, BundleManifest, SECTION_PATHS


def _sections() -> dict:
    return {
        "world": {"world_uid": "w-test", "name": "Мир", "settings": {"b": 2, "a": 1}},
        "locations": [{"location_uid": "loc-1", "parent_location_uid": None}],
        "states": [],
        "connection_nodes": [],
        "connection_edges": [],
        "relief_templates": [{"system_name": "hill", "heights": [2, 1, 0]}],
        "building_templates": [],
        "race_templates": [],
        "perk_templates": [],
    }


def _manifest(sections: dict) -> BundleManifest:
    return BundleManifest.model_validate({
        "kind": "world", "format_version": 1,
        "source": {
            "kind": "world", "world_uid": "w-test", "world_name": "Мир",
            "exporter": "test-exporter", "exported_at": "2026-10-11T18:00:00Z",
        },
        "sections": {key: SECTION_PATHS[key] for key in sections},
    })


class TestBundleArchive(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "world.wpack"

    def _raw_entries(self) -> list[tuple[str, bytes]]:
        sections = _sections()
        return [
            (BundleArchiveLayout.MANIFEST, _manifest(sections).model_dump_json().encode()),
            *((SECTION_PATHS[key], json.dumps(value).encode()) for key, value in sections.items()),
        ]

    def _raw_archive(self, entries=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.path, "w") as archive:
                for name, payload in entries if entries is not None else self._raw_entries():
                    info = ZipInfo(name)
                    # ZipInfo normalizes backslashes on Windows; fixtures must
                    # retain the hostile spelling actually present on the wire.
                    info.filename = name
                    info.orig_filename = name
                    archive.writestr(info, payload)

    def test_skeleton_round_trip_all_sections(self):
        sections = _sections()
        manifest = _manifest(sections)
        self.assertEqual(write_archive(sections, manifest, path=self.path), self.path)
        result = read_archive(self.path)
        self.assertEqual(result.manifest, manifest)
        self.assertEqual(result.sections, sections)
        self.assertEqual(result.blobs, {})

    def test_registry_round_trip(self):
        sections = {"world": _sections()["world"]}
        write_archive(sections, _manifest(sections), path=self.path)
        self.assertEqual(read_archive(self.path).sections, sections)

    def test_byte_reproducibility_independent_of_dict_insertion_order(self):
        sections = _sections()
        manifest = _manifest(sections)
        write_archive(sections, manifest, path=self.path)
        first = self.path.read_bytes()
        reversed_sections = dict(reversed(list(sections.items())))
        reversed_sections["world"] = dict(reversed(list(sections["world"].items())))
        reversed_sections["world"]["settings"] = {"a": 1, "b": 2}
        reversed_manifest = manifest.model_dump(mode="python")
        reversed_manifest["sections"] = dict(reversed(list(manifest.sections.items())))
        write_archive(
            reversed_sections, BundleManifest.model_validate(reversed_manifest), path=self.path,
        )
        self.assertEqual(self.path.read_bytes(), first)

    def test_changed_export_timestamp_changes_archive(self):
        sections = _sections()
        manifest = _manifest(sections)
        write_archive(sections, manifest, path=self.path)
        first = self.path.read_bytes()
        wire = manifest.model_dump(mode="json")
        wire["source"]["exported_at"] = "2026-10-11T18:00:01Z"
        write_archive(sections, BundleManifest.model_validate(wire), path=self.path)
        self.assertNotEqual(self.path.read_bytes(), first)

    def test_zip_metadata_and_compression(self):
        sections = _sections()
        blobs = {
            "pack/tiles/r.0.0.world_map.zst": b"already-compressed-\x00\xff",
            "pack/manifest.json": b'{"version":1}',
            "pack/opaque.bin": b"\x00\x01",
        }
        write_archive(sections, _manifest(sections), blobs, path=self.path)
        with ZipFile(self.path) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            for entry in archive.infolist():
                self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(entry.create_system, 3)
                self.assertEqual(entry.comment, b"")
                self.assertEqual(entry.extra, b"")
                self.assertEqual(entry.external_attr >> 16, 0o100644)
                compression = ZIP_DEFLATED if entry.filename.endswith(".json") else ZIP_STORED
                self.assertEqual(entry.compress_type, compression)
        self.assertEqual(read_archive(self.path, blob_paths=tuple(blobs)).blobs, blobs)
        with self.assertRaisesRegex(BundleArchiveError, "Unknown archive files"):
            read_archive(self.path)

    def test_library_blob_allowlist_preserves_bytes(self):
        sections = _sections()
        blobs = {"library/relief_templates/test/pack.manifest.json": b"{}"}
        write_archive(sections, _manifest(sections), blobs, path=self.path)
        self.assertEqual(read_archive(self.path, blob_paths=tuple(blobs)).blobs, blobs)

    def test_unknown_file_rejected_before_invalid_section_json(self):
        entries = self._raw_entries()
        entries = [(name, b"broken" if name == SECTION_PATHS["locations"] else body)
                   for name, body in entries]
        self._raw_archive(entries + [("unexpected.json", b"{}")])
        with self.assertRaisesRegex(BundleArchiveError, "Unknown archive files"):
            read_archive(self.path)

    def test_missing_manifest_and_missing_indexed_file(self):
        for missing in (BundleArchiveLayout.MANIFEST, SECTION_PATHS["locations"]):
            with self.subTest(missing=missing):
                self._raw_archive([(name, body) for name, body in self._raw_entries() if name != missing])
                with self.assertRaisesRegex(BundleArchiveError, "Missing"):
                    read_archive(self.path)

    def test_unindexed_known_section_is_unknown_file(self):
        sections = {"world": _sections()["world"]}
        write_archive(sections, _manifest(sections), path=self.path)
        with ZipFile(self.path, "a") as archive:
            archive.writestr(SECTION_PATHS["locations"], b"[]")
        with self.assertRaisesRegex(BundleArchiveError, "Unknown archive files"):
            read_archive(self.path)

    def test_invalid_manifest_rejected_before_sections(self):
        manifest_path = BundleArchiveLayout.MANIFEST
        for payload in (b"{", b"[]", b"null", b"{}", b'{"format_version":2}'):
            with self.subTest(payload=payload):
                self._raw_archive([(manifest_path, payload), (SECTION_PATHS["world"], b"broken")])
                with self.assertRaisesRegex(BundleArchiveError, "manifest"):
                    read_archive(self.path)

    def test_malformed_json_utf8_duplicates_and_nonfinite_rejected(self):
        for payload in (b"{", b"\xff", b'{"a":1,"a":2}', b"NaN", b"Infinity"):
            with self.subTest(payload=payload):
                entries = [(name, payload if name == SECTION_PATHS["locations"] else body)
                           for name, body in self._raw_entries()]
                self._raw_archive(entries)
                with self.assertRaisesRegex(BundleArchiveError, "Invalid JSON"):
                    read_archive(self.path)

    def test_duplicate_manifest_keys_rejected(self):
        self._raw_archive([(BundleArchiveLayout.MANIFEST, b'{"kind":"world","kind":"library_pack"}')])
        with self.assertRaisesRegex(BundleArchiveError, "duplicate JSON key"):
            read_archive(self.path)

    def test_duplicate_zip_entries_rejected(self):
        self._raw_archive(self._raw_entries() + [(SECTION_PATHS["world"], b"{}")])
        with self.assertRaisesRegex(BundleArchiveError, "Duplicate archive entry"):
            read_archive(self.path)

    def test_unsafe_paths_rejected(self):
        for path in (
            "../outside.json", "/outside.json", "C:/outside.json", "C:outside.json",
            "pack\\outside.zst", "pack/../outside.zst", "pack//outside.zst", "pack/./outside.zst",
        ):
            with self.subTest(path=path):
                self._raw_archive(self._raw_entries() + [(path, b"x")])
                with self.assertRaisesRegex(BundleArchiveError, "Invalid archive path"):
                    read_archive(self.path)

    def test_symlinks_and_special_files_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO):
            with self.subTest(mode=mode):
                self._raw_archive()
                info = ZipInfo("pack/link.zst")
                info.create_system = 3
                info.external_attr = (mode | 0o777) << 16
                with ZipFile(self.path, "a") as archive:
                    archive.writestr(info, b"../../outside")
                with self.assertRaisesRegex(BundleArchiveError, "Unsupported archive entry type"):
                    read_archive(self.path, blob_paths=(info.filename,))

    def test_only_parent_directory_entries_accepted(self):
        self._raw_archive(self._raw_entries() + [("skeleton/", b"")])
        self.assertEqual(read_archive(self.path).sections, _sections())
        for name in ("unknown/", "pack/", "skeleton/world.json/"):
            with self.subTest(name=name):
                self._raw_archive(self._raw_entries() + [(name, b"")])
                with self.assertRaisesRegex(BundleArchiveError, "Unknown archive directories"):
                    read_archive(self.path)

    def test_directory_entries_cannot_hide_data(self):
        self._raw_archive(self._raw_entries() + [("skeleton/", b"hidden payload")])
        with self.assertRaisesRegex(BundleArchiveError, "Directory entry contains data"):
            read_archive(self.path)

    def test_corrupt_zip_and_corrupt_crc_rejected(self):
        self.path.write_bytes(b"not a zip")
        with self.assertRaises(BundleArchiveError):
            read_archive(self.path)
        self._raw_archive()
        data = self.path.read_bytes()
        # Stored section bytes are changed while preserving original ZIP CRC.
        needle = b'"location_uid": "loc-1"'
        self.assertIn(needle, data)
        self.path.write_bytes(data.replace(needle, b'"location_uid": "loc-2"', 1))
        with self.assertRaisesRegex(BundleArchiveError, "Cannot read bundle archive"):
            read_archive(self.path)

    def test_source_identity_must_match_world_on_write_and_read(self):
        sections = _sections()
        manifest = _manifest(sections)
        sections["world"]["world_uid"] = "w-other"
        with self.assertRaisesRegex(BundleArchiveError, "source.world_uid"):
            write_archive(sections, manifest, path=self.path)
        entries = [(name, body.replace(b"w-test", b"w-other") if name == SECTION_PATHS["world"] else body)
                   for name, body in self._raw_entries()]
        self._raw_archive(entries)
        with self.assertRaisesRegex(BundleArchiveError, "source.world_uid"):
            read_archive(self.path)

    def test_world_section_must_be_object(self):
        sections = _sections()
        manifest = _manifest(sections)
        sections["world"] = []
        with self.assertRaisesRegex(BundleArchiveError, "World section must be an object"):
            write_archive(sections, manifest, path=self.path)

    def test_writer_rejects_section_index_mismatch_and_mutated_manifest(self):
        sections = _sections()
        manifest = _manifest(sections)
        for invalid in ({**sections, "unknown": []}, {"world": sections["world"]}):
            with self.assertRaisesRegex(BundleArchiveError, "match the manifest"):
                write_archive(invalid, manifest, path=self.path)
        manifest.sections["world"] = "../world.json"
        with self.assertRaisesRegex(BundleArchiveError, "Invalid bundle manifest"):
            write_archive(sections, manifest, path=self.path)

    def test_invalid_writer_input_leaves_existing_file_and_no_temp_files(self):
        self.path.write_bytes(b"original")
        sections = _sections()
        manifest = _manifest(sections)
        for invalid in (float("nan"), object()):
            sections["locations"] = invalid
            with self.assertRaisesRegex(BundleArchiveError, "Cannot encode JSON"):
                write_archive(sections, manifest, path=self.path)
            self.assertEqual(self.path.read_bytes(), b"original")
            self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_atomic_write_failure_cleans_temporary_file(self):
        sections = _sections()
        self.path.write_bytes(b"original")
        with patch(
            "app.application.worldData.bundle.archive.writer.ZipFile.writestr",
            side_effect=OSError("simulated disk failure"),
        ):
            with self.assertRaises(OSError):
                write_archive(sections, _manifest(sections), path=self.path)
        self.assertEqual(self.path.read_bytes(), b"original")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_blob_paths_require_exact_safe_layout(self):
        sections = _sections()
        for name in ("unknown.bin", "skeleton/world.json", "pack/../escape.zst", "pack/"):
            with self.subTest(name=name):
                with self.assertRaises(BundleArchiveError):
                    write_archive(sections, _manifest(sections), {name: b"x"}, path=self.path)
        write_archive(sections, _manifest(sections), path=self.path)
        with self.assertRaisesRegex(BundleArchiveError, "Missing archive files"):
            read_archive(self.path, blob_paths=("pack/missing.zst",))
        with self.assertRaisesRegex(BundleArchiveError, "Duplicate blob paths"):
            read_archive(self.path, blob_paths=("pack/a.zst", "pack/a.zst"))

    def test_blob_payload_must_be_bytes(self):
        sections = _sections()
        with self.assertRaisesRegex(BundleArchiveError, "must be bytes"):
            write_archive(sections, _manifest(sections), {"pack/a.zst": "text"}, path=self.path)

    def test_blob_file_cannot_be_a_parent_directory(self):
        sections = _sections()
        with self.assertRaisesRegex(BundleArchiveError, "also used as a parent directory"):
            write_archive(
                sections, _manifest(sections),
                {"pack/a": b"x", "pack/a/b.zst": b"y"}, path=self.path,
            )


if __name__ == "__main__":
    unittest.main()
