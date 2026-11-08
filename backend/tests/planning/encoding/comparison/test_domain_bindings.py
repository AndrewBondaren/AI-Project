"""Compare each owner's declarations against its pre-split TLV identities."""
import unittest
from importlib import import_module
from pathlib import Path


def logical_type(owner):
    metadata = getattr(owner, "__pydantic_generic_metadata__", None)
    if metadata and (origin := metadata["origin"]):
        arguments = metadata["args"]
        assert origin[arguments] is owner
        return f"{origin.__module__}.{origin.model_parametrized_name(arguments)}"
    return f"{owner.__module__}.{owner.__qualname__}"


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
                actual = {identity: (kind.value, logical_type(owner))
                          for identity, owner, kind in bindings}
                self.assertEqual(len(actual), len(bindings))
                self.assertEqual(actual.keys(), expected.keys())
                for identity, value in expected.items():
                    with self.subTest(type_id=identity):
                        self.assertEqual(actual[identity], value)
