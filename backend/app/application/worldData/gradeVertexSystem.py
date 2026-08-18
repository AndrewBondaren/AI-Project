"""T-3c: ≥2 Instance of one vertex → ReliefGradeSystem.

Intra-chunk groups = discover slots. Across chunks of this refine: body cells
on internal C29 faces, 8-adjacent at the same integer z, then union-find slots
and emit once. Catalog ``face_key`` is not a vertex slot.
SoT: ``docs/tz_terrain_relief.md`` § T-3c на шве чанков.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    build_relief_grade_system,
)
from app.application.worldData.pack.refine.columnBounds import ColumnBounds
from app.application.worldData.pack.refine.detailedGradeCatalog import FaceKey, TileFaceCatalog
from app.application.worldData.pack.refine.fineTileContext import VertexSlotSeam
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.dataModel.worldPack.packJobUid import FaceGridAxis

SlotKey = tuple[int, int, int]
ChunkTrace = tuple[ColumnBounds, Sequence[VertexSlotSeam]]


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[SlotKey, SlotKey] = {}

    def add(self, key: SlotKey) -> None:
        self._parent.setdefault(key, key)

    def find(self, key: SlotKey) -> SlotKey:
        parent = self._parent[key]
        if parent != key:
            parent = self.find(parent)
            self._parent[key] = parent
        return parent

    def union(self, left: SlotKey, right: SlotKey) -> None:
        root_l = self.find(left)
        root_r = self.find(right)
        if root_l == root_r:
            return
        if root_l < root_r:
            self._parent[root_r] = root_l
        else:
            self._parent[root_l] = root_r


def emit_relief_grade_systems(
    instances: Sequence[ReliefGradeInstance],
    traces: Sequence[ChunkTrace],
    catalog: TileFaceCatalog | None,
) -> tuple[tuple[ReliefGradeInstance, ...], tuple[ReliefGradeSystem, ...]]:
    """After ``merge_grade_instances``: slot groups + C29 body match → System iff ≥2 uid."""
    merged = {inst.grade_uid: inst for inst in instances}
    if not merged:
        return (), ()

    slot_uids: dict[SlotKey, tuple[str, ...]] = {}
    by_chunk: dict[tuple[int, int], list[SlotKey]] = defaultdict(list)
    edge_of: dict[SlotKey, tuple[tuple[int, int, int], ...]] = {}
    present: set[tuple[int, int]] = set()

    for rect, seams in traces:
        cx, cy = _chunk_xy(catalog, rect)
        present.add((cx, cy))
        for seam in seams:
            uids = tuple(
                uid for uid in seam.grade_uids
                if uid in merged
            )
            # Catalog merge can collapse two fronts of one straight to one uid.
            uids = tuple(dict.fromkeys(uids))
            if not uids:
                continue
            key = (cx, cy, int(seam.slot))
            slot_uids[key] = uids
            edge_of[key] = tuple(seam.edge_body)
            by_chunk[(cx, cy)].append(key)

    uf = _UnionFind()
    for key in slot_uids:
        uf.add(key)

    if catalog is not None:
        for face in _internal_faces(catalog):
            parents = catalog.chunk_parents(face)
            if len(parents) != 2:
                continue
            lo_xy, hi_xy = parents
            if lo_xy not in present or hi_xy not in present:
                continue
            lo_coord, hi_coord, axis = _seam_line(catalog, face)
            for left in by_chunk.get(lo_xy, ()):
                left_cells = _on_seam(edge_of[left], lo_coord, axis)
                if not left_cells:
                    continue
                for right in by_chunk.get(hi_xy, ()):
                    right_cells = _on_seam(edge_of[right], hi_coord, axis)
                    if _bodies_touch_8(left_cells, right_cells):
                        uf.union(left, right)

    groups: dict[SlotKey, list[SlotKey]] = defaultdict(list)
    for key in slot_uids:
        groups[uf.find(key)].append(key)

    uid_to_system: dict[str, str] = {}
    systems: list[ReliefGradeSystem] = []
    seen_uid_sets: set[tuple[str, ...]] = set()
    for members in groups.values():
        unique: list[str] = []
        found: set[str] = set()
        for key in members:
            for uid in slot_uids[key]:
                if uid not in found:
                    found.add(uid)
                    unique.append(uid)
        unique.sort()
        if len(unique) < 2:
            continue
        uid_key = tuple(unique)
        if uid_key in seen_uid_sets:
            continue
        seen_uid_sets.add(uid_key)
        grades = [merged[uid] for uid in unique]
        world_uid = grades[0].world_uid
        site_id = "|".join(unique)
        system = build_relief_grade_system(
            world_uid=world_uid,
            site_id=site_id,
            grades=grades,
            why="t3c_same_vertex",
        )
        systems.append(system)
        for uid in unique:
            uid_to_system[uid] = system.grade_system_uid

    systems.sort(key=lambda sys: sys.grade_system_uid)
    out_instances = tuple(
        inst.model_copy(update={"grade_system_uid": uid_to_system[inst.grade_uid]})
        if inst.grade_uid in uid_to_system
        else inst
        for inst in instances
        if inst.grade_uid in merged
    )
    return out_instances, tuple(systems)


def _chunk_xy(
    catalog: TileFaceCatalog | None,
    rect: ColumnBounds,
) -> tuple[int, int]:
    if catalog is not None:
        return catalog.chunk_of_rect(rect)
    return (rect.x_min, rect.y_min)


def _internal_faces(catalog: TileFaceCatalog) -> tuple[FaceKey, ...]:
    faces: list[FaceKey] = []
    for cy in range(catalog.n_cy):
        for cx in range(max(0, catalog.n_cx - 1)):
            faces.append(FaceKey(FaceGridAxis.V, cx, cy))
    for cy in range(max(0, catalog.n_cy - 1)):
        for cx in range(catalog.n_cx):
            faces.append(FaceKey(FaceGridAxis.H, cx, cy))
    return tuple(faces)


def _seam_line(
    catalog: TileFaceCatalog,
    face: FaceKey,
) -> tuple[int, int, str]:
    if face.axis == FaceGridAxis.V:
        lo = catalog.origin_x + (face.cx + 1) * catalog.chunk_size - 1
        return lo, lo + 1, "x"
    lo = catalog.origin_y + (face.cy + 1) * catalog.chunk_size - 1
    return lo, lo + 1, "y"


def _on_seam(
    edge_body: Sequence[tuple[int, int, int]],
    coord: int,
    axis: str,
) -> tuple[tuple[int, int, int], ...]:
    index = 0 if axis == "x" else 1
    return tuple(cell for cell in edge_body if cell[index] == coord)


def _bodies_touch_8(
    left: Sequence[tuple[int, int, int]],
    right: Sequence[tuple[int, int, int]],
) -> bool:
    if not left or not right:
        return False
    by_z: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for x, y, z in right:
        by_z[int(z)].append((int(x), int(y)))
    for x, y, z in left:
        for rx, ry in by_z.get(int(z), ()):
            if max(abs(int(x) - rx), abs(int(y) - ry)) == 1:
                return True
    return False
