"""Compare each owner's declarations against its pre-split TLV identities."""
import unittest
from importlib import import_module
from pathlib import Path


class DomainBindingsTests(unittest.TestCase):
    def test_registered_types_by_domain(self):
        fixtures = Path(__file__).with_name("fixtures")
        paths = sorted(fixtures.glob("*/*.tsv"))
        self.assertEqual(len(paths), 18)
        for path in paths:
            module, *lines = path.read_text(encoding="utf-8").splitlines()
            with self.subTest(domain=module):
                expected = {}
                for line in lines:
                    identity, kind, owner = line.split("\t")
                    self.assertNotIn(int(identity), expected)
                    expected[int(identity)] = (kind, owner)
                bindings = import_module(module).BINDINGS
                actual = {identity: (kind.value, f"{owner.__module__}.{owner.__qualname__}")
                          for identity, owner, kind in bindings}
                self.assertEqual(len(actual), len(bindings))
                self.assertEqual(actual.keys(), expected.keys())
                for identity, value in expected.items():
                    with self.subTest(type_id=identity):
                        self.assertEqual(actual[identity], value)
