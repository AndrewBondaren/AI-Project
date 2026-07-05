"""with_default_created_at — optional on wire for bundle entities."""

from __future__ import annotations

import unittest
from datetime import datetime

from app.application.import_helpers import with_default_created_at


class ImportCreatedAtDefaultTests(unittest.TestCase):
    def test_injects_local_iso_when_missing(self) -> None:
        row = with_default_created_at({"display_name": "Test"})
        self.assertIn("created_at", row)
        datetime.fromisoformat(row["created_at"])

    def test_preserves_explicit_value(self) -> None:
        row = with_default_created_at({"created_at": "2020-01-01T00:00:00"})
        self.assertEqual(row["created_at"], "2020-01-01T00:00:00")


if __name__ == "__main__":
    unittest.main()
