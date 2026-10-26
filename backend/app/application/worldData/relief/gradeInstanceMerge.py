"""Single union for grade cell_refs / instances — R36v-T-5."""

from __future__ import annotations

from collections.abc import Iterable

from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance

Coord = tuple[int, int]


def merge_cell_refs(*groups: Iterable[object]) -> list[Coord]:
    """Stable union; accepts instance tuples or SQL ``[[x, y], …]``. Order: sorted xy."""
    seen: set[Coord] = set()
    for group in groups:
        for pair in group:
            seen.add((int(pair[0]), int(pair[1])))
    return sorted(seen)


def apply_prior_cell_refs(
    inst: ReliefGradeInstance,
    prior_refs: Iterable[object] | None,
) -> ReliefGradeInstance:
    """Union prior SQL/instance refs onto ``inst`` (upsert policy)."""
    if not prior_refs:
        return inst
    return inst.model_copy(
        update={"cell_refs": merge_cell_refs(prior_refs, inst.cell_refs)},
    )


def merge_grade_instances(
    instances: list[ReliefGradeInstance] | tuple[ReliefGradeInstance, ...],
) -> tuple[ReliefGradeInstance, ...]:
    """Same uid: last instance wins fields; ``cell_refs`` union (SQL upsert)."""
    by_uid: dict[str, ReliefGradeInstance] = {}
    for inst in instances:
        prev = by_uid.get(inst.grade_uid)
        if prev is None:
            by_uid[inst.grade_uid] = inst
            continue
        refs = merge_cell_refs(prev.cell_refs, inst.cell_refs)
        by_uid[inst.grade_uid] = inst.model_copy(update={"cell_refs": refs})
    return tuple(by_uid.values())
