"""Pack grade-ray file I/O — sender + receiver slots, not a FineTerrain blob.

SoT: ``docs/tz_terrain_relief_consume.md``. Wire = ``GradeRaySidecar``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRaySidecar,
    GradeRimRay,
    merge_grade_rim_rays,
)


def load_grade_ray_sidecar(path: Path) -> tuple[GradeRimRay, ...]:
    if not path.is_file():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return GradeRaySidecar.model_validate(raw).rays


def write_grade_ray_sidecar(path: Path, rays: Iterable[GradeRimRay]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = GradeRaySidecar(rays=tuple(rays)).model_dump(mode="json")
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_grade_ray_sidecar(path: Path, rays: Iterable[GradeRimRay]) -> tuple[GradeRimRay, ...]:
    merged = merge_grade_rim_rays(load_grade_ray_sidecar(path), rays)
    write_grade_ray_sidecar(path, merged)
    return merged
