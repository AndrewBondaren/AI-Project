"""C28 face-graph stitch — topology then remap uid. Does not mint. No System (T-3c).

Deprecated v1 occupancy graph (seed union-find before the pool). Catalog
``face_key`` identity remains SoT (R36w). Discover SoT is R41
(``.cursor/plans/relief-pipeline-v2.md``).
"""

from __future__ import annotations

from dataclasses import replace

from app.application.worldData.generators.terrain.relief.geom.facing import CARDINAL_ORTHO_DELTAS
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.pack.refine.detailedGradeCatalog import (
    FaceKey,
    TileFaceCatalog,
    seed_ref_axis,
)
from app.application.worldData.pack.refine.detailedGradePlan import (
    GradeStraightKey,
    PlannedGradeSegment,
    split_mixed_outward,
    straight_key,
)
from app.application.worldData.pack.refine.meterGradeSurface import Coord


def face_vertices(face: FaceKey) -> tuple[Coord, Coord]:
    return face.vertices()


def faces_share_vertex(left: FaceKey, right: FaceKey) -> bool:
    return bool(set(left.vertices()) & set(right.vertices()))


def faces_for_segment(
    catalog: TileFaceCatalog,
    item: PlannedGradeSegment,
) -> tuple[FaceKey, ...]:
    return catalog.faces_for_cells(item.result.segment.cell_coords)


def _seeds_adjacent_same_terrain(
    left: PlannedGradeSegment,
    right: PlannedGradeSegment,
) -> bool:
    if left.result.segment.system_terrain != right.result.segment.system_terrain:
        return False
    other = set(right.result.segment.cell_coords)
    for x, y in left.result.segment.cell_coords:
        for dx, dy in CARDINAL_ORTHO_DELTAS:
            if (x + dx, y + dy) in other:
                return True
    return False


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self._parent.setdefault(key, key)

    def find(self, key: str) -> str:
        parent = self._parent[key]
        if parent != key:
            parent = self.find(parent)
            self._parent[key] = parent
        return parent

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _union_all_faces(uf: _UnionFind, faces: tuple[FaceKey, ...]) -> None:
    """All catalog faces of one occupancy row are one topology node-set."""
    if not faces:
        return
    root = faces[0].wire()
    uf.add(root)
    for face in faces[1:]:
        uf.add(face.wire())
        uf.union(root, face.wire())


def build_face_components(
    catalog: TileFaceCatalog,
    planned: list[PlannedGradeSegment],
) -> tuple[list[tuple[FaceKey, ...]], _UnionFind]:
    faces_of = [faces_for_segment(catalog, item) for item in planned]
    uf = _UnionFind()
    for faces in faces_of:
        _union_all_faces(uf, faces)
    n = len(planned)
    for i in range(n):
        if not faces_of[i]:
            continue
        for j in range(i + 1, n):
            if not faces_of[j]:
                continue
            if not _seeds_adjacent_same_terrain(planned[i], planned[j]):
                continue
            if not any(
                faces_share_vertex(a, b) for a in faces_of[i] for b in faces_of[j]
            ):
                continue
            uf.union(faces_of[i][0].wire(), faces_of[j][0].wire())
    return faces_of, uf


def group_straights(
    planned: list[PlannedGradeSegment],
    faces_of: list[tuple[FaceKey, ...]],
    uf: _UnionFind,
) -> dict[tuple[str, GradeStraightKey], list[int]]:
    groups: dict[tuple[str, GradeStraightKey], list[int]] = {}
    for i, item in enumerate(planned):
        faces = faces_of[i]
        key = straight_key(item)
        if not faces or key is None:
            continue
        root = uf.find(faces[0].wire())
        groups.setdefault((root, key), []).append(i)
    return groups


def remap_straight_uids(
    catalog: TileFaceCatalog,
    planned: list[PlannedGradeSegment],
    faces_of: list[tuple[FaceKey, ...]],
    groups: dict[tuple[str, GradeStraightKey], list[int]],
) -> list[PlannedGradeSegment]:
    remapped = list(planned)
    changed = 0
    for (_root, _key), indexes in groups.items():
        face_bag: list[FaceKey] = []
        seeds: list[Coord] = []
        refs: set[Coord] = set()
        for i in indexes:
            face_bag.extend(faces_of[i])
            seeds.extend(remapped[i].result.segment.cell_coords)
            refs.update(remapped[i].ref_cells)
        uid = catalog.uid_for_faces(face_bag, axis=seed_ref_axis(seeds, refs))
        if uid is None:
            continue
        for i in indexes:
            if remapped[i].grade_uid == uid:
                continue
            remapped[i] = replace(remapped[i], grade_uid=uid)
            changed += 1
    if changed:
        relief_debug(
            "grade_face_graph_stitch",
            tile_uid=catalog.macro_tile_uid(),
            segments=len(planned),
            straights=len(groups),
            remapped=changed,
        )
    return remapped


def stitch_planned_segments(
    catalog: TileFaceCatalog,
    planned: list[PlannedGradeSegment],
) -> list[PlannedGradeSegment]:
    """Deprecated v1: remap face-touching segments to one uid per component × straight.

    Graph edges do not mint uid. Interior-only segments keep ``interior|{k}``.
    SoT stitch is after chunks, by catalog uid (R41), not this pre-pool UF.
    """
    if not planned:
        return planned
    expanded: list[PlannedGradeSegment] = []
    for item in planned:
        if item.grade_uid:
            expanded.append(item)
            continue
        expanded.extend(split_mixed_outward(item))
    faces_of, uf = build_face_components(catalog, expanded)
    groups = group_straights(expanded, faces_of, uf)
    return remap_straight_uids(catalog, expanded, faces_of, groups)
