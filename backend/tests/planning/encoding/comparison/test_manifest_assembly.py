"""The assembled manifest must retain each declaring domain's exact class."""
import unittest
from importlib import import_module
from pathlib import Path

from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST


class ManifestAssemblyTests(unittest.TestCase):
    def test_global_order_and_unique_bindings(self):
        expected = {}
        for path in Path(__file__).with_name("fixtures").glob("*/*.tsv"):
            module = path.read_text(encoding="utf-8").splitlines()[0]
            for identity, owner, kind in import_module(module).BINDINGS:
                self.assertNotIn(identity, expected, f"duplicate ID in {module}")
                expected[identity] = owner, kind

        entries = SURFACE_MANIFEST.entries
        self.assertEqual(len(expected), 343)
        self.assertEqual([entry.type_id for entry in entries], sorted(expected))
        self.assertEqual(len({entry.python_type for entry in entries}), len(entries))
        for entry in entries:
            with self.subTest(type_id=entry.type_id):
                owner, kind = expected[entry.type_id]
                self.assertIs(entry.python_type, owner)
                self.assertIs(entry.kind, kind)
