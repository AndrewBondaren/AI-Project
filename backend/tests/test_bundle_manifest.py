"""Archive manifest contract — C-2 / tz_template_library_packs §4.2."""

import unittest

from pydantic import ValidationError

from app.dataModel.worldBundle import (
    BundleArchiveLayout,
    BundleKind,
    BundleLibraryPackSource,
    BundleManifest,
    BundleSection,
    BundleWorldSource,
    PATH_SECTIONS,
    SECTION_PATHS,
)


def _world_manifest() -> dict:
    return {
        "kind": "world",
        "format_version": 1,
        "source": {
            "kind": "world",
            "world_uid": "w-test",
            "world_name": "Test World",
            "exporter": "test-exporter",
            "exported_at": "2026-10-11T18:00:00Z",
        },
        "sections": dict(SECTION_PATHS),
    }


def _pack_manifest() -> dict:
    return {
        "kind": "library_pack",
        "format_version": 1,
        "source": {
            "kind": "library_pack",
            "pack_uid": "p-test",
            "exporter": "test-exporter",
            "exported_at": "2026-10-11T18:00:00+00:00",
        },
        "sections": {},
    }


class TestBundleManifest(unittest.TestCase):
    def test_round_trip_both_archive_kinds(self):
        for wire, source_type in (
            (_world_manifest(), BundleWorldSource),
            (_pack_manifest(), BundleLibraryPackSource),
        ):
            with self.subTest(kind=wire["kind"]):
                manifest = BundleManifest.model_validate(wire)
                self.assertIsInstance(manifest.source, source_type)
                self.assertIsInstance(manifest.kind, BundleKind)
                self.assertIsInstance(manifest.source.kind, BundleKind)
                dumped = manifest.model_dump(mode="json")
                self.assertEqual(dumped["kind"], wire["kind"])
                self.assertIs(type(dumped["kind"]), str)
                self.assertEqual(dumped["source"]["kind"], wire["source"]["kind"])
                self.assertIs(type(dumped["source"]["kind"]), str)
                self.assertEqual(
                    BundleManifest.model_validate_json(manifest.model_dump_json()),
                    manifest,
                )
                self.assertEqual(
                    BundleManifest.model_validate(manifest.model_dump(mode="json")),
                    manifest,
                )

    def test_registry_and_partial_skeleton_are_valid(self):
        wire = _world_manifest()
        wire["sections"] = {"world": "skeleton/world.json"}
        BundleManifest.model_validate(wire)
        wire["sections"]["locations"] = "skeleton/locations.json"
        BundleManifest.model_validate(wire)

    def test_layout_covers_all_skeleton_sections_bijectively(self):
        self.assertEqual(set(SECTION_PATHS), BundleSection.SKELETON)
        self.assertEqual(len(SECTION_PATHS), 9)
        self.assertEqual(len(PATH_SECTIONS), len(SECTION_PATHS))
        for section, path in SECTION_PATHS.items():
            self.assertEqual(PATH_SECTIONS[path], section)
            self.assertTrue(path.startswith(BundleArchiveLayout.SKELETON_PREFIX))
        with self.assertRaises(TypeError):
            SECTION_PATHS["invented"] = "skeleton/invented.json"
        with self.assertRaises(TypeError):
            PATH_SECTIONS["skeleton/invented.json"] = "invented"

    def test_file_subtrees_are_not_section_keys(self):
        self.assertEqual(BundleArchiveLayout.MANIFEST, "bundle.manifest.json")
        self.assertEqual(BundleArchiveLayout.LIBRARY_PREFIX, "library/")
        self.assertEqual(BundleArchiveLayout.PACK_PREFIX, "pack/")
        for key, path in (("library", "library/"), ("pack", "pack/")):
            with self.subTest(key=key):
                wire = _world_manifest()
                wire["sections"][key] = path
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)

    def test_unknown_and_unsafe_section_paths_rejected(self):
        for key, path in (
            ("unknown", "skeleton/unknown.json"),
            ("world", "skeleton/states.json"),
            ("world", "../world.json"),
            ("world", "/skeleton/world.json"),
            ("world", "skeleton\\world.json"),
            ("world", "skeleton//world.json"),
            ("world", "skeleton/./world.json"),
            ("world", "C:/skeleton/world.json"),
            ("world", "library/world.json"),
        ):
            with self.subTest(key=key, path=path):
                wire = _world_manifest()
                wire["sections"][key] = path
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)

    def test_unknown_version_and_non_integer_version_rejected(self):
        for version in (0, 2, True, 1.0, "1", None):
            with self.subTest(version=version):
                wire = _world_manifest()
                wire["format_version"] = version
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)

    def test_required_root_and_source_fields(self):
        for wire in (_world_manifest(), _pack_manifest()):
            for key in wire:
                with self.subTest(kind=wire["kind"], missing=key):
                    broken = {k: v for k, v in wire.items() if k != key}
                    with self.assertRaises(ValidationError):
                        BundleManifest.model_validate(broken)
            for key in wire["source"]:
                with self.subTest(kind=wire["kind"], missing_source=key):
                    broken = {**wire, "source": {
                        k: v for k, v in wire["source"].items() if k != key
                    }}
                    with self.assertRaises(ValidationError):
                        BundleManifest.model_validate(broken)

    def test_source_kind_must_match_archive_kind(self):
        for wire, other in (
            (_world_manifest(), _pack_manifest()),
            (_pack_manifest(), _world_manifest()),
        ):
            wire["source"] = other["source"]
            with self.assertRaises(ValidationError):
                BundleManifest.model_validate(wire)

    def test_unknown_archive_and_source_kinds_rejected(self):
        for field in ("kind", "source"):
            wire = _world_manifest()
            if field == "kind":
                wire["kind"] = "unknown"
            else:
                wire["source"]["kind"] = "unknown"
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)

    def test_world_section_required_and_pack_sections_empty(self):
        wire = _world_manifest()
        wire["sections"].pop("world")
        with self.assertRaises(ValidationError):
            BundleManifest.model_validate(wire)
        wire = _pack_manifest()
        wire["sections"] = {"world": "skeleton/world.json"}
        with self.assertRaises(ValidationError):
            BundleManifest.model_validate(wire)

    def test_source_requires_nonempty_strings_and_utc_time(self):
        for key, value in (
            ("world_uid", ""), ("world_uid", "  "), ("world_uid", 123),
            ("world_name", ""), ("exporter", ""),
            ("exported_at", "2026-10-11T18:00:00"),
            ("exported_at", "2026-10-11T18:00:00+03:00"),
            ("exported_at", 1791741600),
        ):
            with self.subTest(key=key, value=value):
                wire = _world_manifest()
                wire["source"][key] = value
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)

    def test_optional_hash_preserved_without_generation(self):
        wire = _world_manifest()
        manifest = BundleManifest.model_validate(wire)
        self.assertIsNone(manifest.source.content_hash)
        wire["source"]["content_hash"] = "opaque-diagnostic-hash"
        self.assertEqual(
            BundleManifest.model_validate(wire).source.content_hash,
            "opaque-diagnostic-hash",
        )

    def test_envelope_rejects_domain_fields_and_wrong_source_fields(self):
        for wire in (
            {**_world_manifest(), "map_settings": {}},
            {**_world_manifest(), "source": {
                **_world_manifest()["source"], "pack_uid": "p-test",
            }},
            {**_pack_manifest(), "source": {
                **_pack_manifest()["source"], "world_uid": "w-test",
            }},
        ):
            with self.subTest(wire=wire):
                with self.assertRaises(ValidationError):
                    BundleManifest.model_validate(wire)


if __name__ == "__main__":
    unittest.main()
