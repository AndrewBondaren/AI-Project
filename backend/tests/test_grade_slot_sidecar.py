"""SCH-GRADE-CELL-SLOTS sidecar I/O — compact JSON, no old rays[]."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.application.worldData.pack.io.gradeSlotSidecar import (
    load_grade_slot_sidecar,
    merge_grade_slot_sidecar,
    write_grade_slot_sidecar,
)
from app.dataModel.terrain.relief.gradeSlot import (
    GradeCellSlots,
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
)


def _pit_ring() -> GradeCellSlots:
    """Яма (0,1)=4 — generate § Pack-слот."""
    return GradeCellSlots(
        x=0,
        y=1,
        slots=(
            GradeSeam.SEAM,
            GradeCouple.COUPLE,
            GradeCouple.COUPLE,
            GradeSeam.SEAM,
            GradeOctant.EAST,
            GradeSeam.SEAM,
            GradeCouple.COUPLE,
            GradeCouple.COUPLE,
        ),
    )


class TestGradeSlotSidecarIo(unittest.TestCase):
    def test_roundtrip_compact_and_ignores_old_rays(self) -> None:
        cell = _pit_ring()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grade_rays.json"
            write_grade_slot_sidecar(path, (cell,))
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("\n  ", text)
            self.assertIn('"schema_id":"SCH-GRADE-CELL-SLOTS"', text)
            loaded = load_grade_slot_sidecar(path)
            self.assertEqual(loaded, (cell,))

            old = Path(tmp) / "old.json"
            old.write_text(
                json.dumps({"rays": [{"x": 0, "y": 0, "facing": "east", "kind": "slope"}]}),
                encoding="utf-8",
            )
            self.assertEqual(load_grade_slot_sidecar(old), ())

    def test_reject_short_slots_and_merge_incoming_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grade_rays.json"
            with self.assertRaises(ValidationError):
                GradeCellSlots(x=0, y=0, slots=(8, 8, 8))
            on_disk = GradeCellSlots(x=1, y=1, slots=(8,) * 8)
            incoming_same = GradeCellSlots(x=1, y=1, slots=(int(GradeSheer.SHEER),) * 8)
            incoming_new = GradeCellSlots(x=2, y=2, slots=(int(GradeCouple.COUPLE),) * 8)
            write_grade_slot_sidecar(path, (on_disk,))
            merged = merge_grade_slot_sidecar(path, (incoming_same, incoming_new))
            by_xy = {c.cell: c for c in merged}
            self.assertEqual(by_xy[(1, 1)].slots[0], int(GradeSheer.SHEER))
            self.assertEqual(by_xy[(2, 2)].slots[0], int(GradeCouple.COUPLE))


if __name__ == "__main__":
    unittest.main()
