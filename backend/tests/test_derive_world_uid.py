"""derive_world_uid — stable fingerprint from normalized world wire."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.facade import normalize_world
from app.application.worldData.deriveWorldUid import derive_world_uid


class DeriveWorldUidTests(unittest.TestCase):
    def test_stable_for_same_content(self) -> None:
        wire = normalize_world({"name": "Test", "created_at": "2026-01-01T00:00:00"})
        a = derive_world_uid(wire)
        b = derive_world_uid(wire)
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("world-"))
        self.assertEqual(len(a), len("world-") + 16)

    def test_created_at_does_not_affect_uid(self) -> None:
        base = {"name": "Test", "map_cell_size_m": 3000}
        a = derive_world_uid(normalize_world({**base, "created_at": "2026-01-01T00:00:00"}))
        b = derive_world_uid(normalize_world({**base, "created_at": "2027-06-01T00:00:00"}))
        self.assertEqual(a, b)

    def test_name_change_changes_uid(self) -> None:
        a = derive_world_uid(normalize_world({"name": "Alpha", "created_at": "2026-01-01T00:00:00"}))
        b = derive_world_uid(normalize_world({"name": "Beta", "created_at": "2026-01-01T00:00:00"}))
        self.assertNotEqual(a, b)

    def test_explicit_world_uid_ignored_in_hash(self) -> None:
        wire = normalize_world({"name": "Test", "created_at": "2026-01-01T00:00:00"})
        with_uid = {**wire, "world_uid": "manual-uid"}
        self.assertEqual(derive_world_uid(wire), derive_world_uid(with_uid))


if __name__ == "__main__":
    unittest.main()
