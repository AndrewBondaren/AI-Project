"""Real user/default library artifacts retain their identity and source content."""

import tempfile
import unittest
from pathlib import Path

from app.application.worldBundle.archive import read_archive
from app.application.templateLibrary.packs.defaults import is_default_pack_uid
from app.dataModel.worldBundle.bundleManifest import BundleKind
from scripts.build_library_test_fixtures import OUTPUT, SOURCES, build, load_fixture_source


class LibraryArchiveFixtureTests(unittest.TestCase):
    def test_real_sources_and_default_identity_match_saved_archives(self):
        expected_counts = {"user_library": 4, "engine_library": 13}
        for name, kind, folder, expected_default in SOURCES:
            with self.subTest(library=name):
                contents = read_archive(OUTPUT / f"{name}.wpack")
                source = load_fixture_source(kind, folder)
                self.assertEqual(contents.manifest.kind, BundleKind.LIBRARY_PACK)
                self.assertEqual(contents.manifest.source.pack_uid, source.manifest.pack_uid)
                self.assertEqual(contents.sections, {})
                self.assertEqual(contents.blobs, {})
                self.assertEqual(contents.library_packs, (source,))
                self.assertEqual(len(source.bodies), expected_counts[name])
                self.assertEqual(is_default_pack_uid(source.manifest.pack_uid), expected_default)

    def test_saved_fixture_bytes_are_reproducible_from_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            for rebuilt in build(Path(directory)):
                self.assertEqual(rebuilt.read_bytes(), (OUTPUT / rebuilt.name).read_bytes())
