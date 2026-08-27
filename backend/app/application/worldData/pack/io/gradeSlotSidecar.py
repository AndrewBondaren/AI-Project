"""Pack grade cell-slot sidecar I/O — ``SCH-GRADE-CELL-SLOTS``.

SoT: ``docs/tz_terrain_relief_consume.md`` § Тело sidecar.
Persist writes this body. Files without this ``schema_id`` (old ``rays[]``) load
as empty. Dump reads this body (``GradeSlotIndex``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_SCHEMA_ID,
    GradeCellSlots,
    GradeSlotSidecar,
    merge_grade_cell_slots,
)


def load_grade_slot_sidecar(path: Path) -> tuple[GradeCellSlots, ...]:
    if not path.is_file():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_id") != GRADE_SLOT_SCHEMA_ID:
        return ()
    return GradeSlotSidecar.model_validate(raw).cells


def write_grade_slot_sidecar(path: Path, cells: Iterable[GradeCellSlots]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = GradeSlotSidecar(cells=tuple(cells)).model_dump(mode="json")
    path.write_text(
        json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def merge_grade_slot_sidecar(
    path: Path,
    cells: Iterable[GradeCellSlots],
) -> tuple[GradeCellSlots, ...]:
    """Incoming bake first-wins on ``(x, y, position)``; file fills empty keys."""
    merged = merge_grade_cell_slots(tuple(cells), load_grade_slot_sidecar(path))
    write_grade_slot_sidecar(path, merged)
    return merged
