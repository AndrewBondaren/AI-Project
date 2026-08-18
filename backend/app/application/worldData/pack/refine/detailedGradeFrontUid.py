"""Inherit / catalog / mint uid for one discovered front (R41-T-9).

Catalog ``face_key`` is identity, not a seed graph. Inherit is ortho only (T-6).
Does not alias ``Coord`` — uses discover types.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    GRID_OUTWARD_DELTA,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    FrontGeometry,
)
from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    make_grade_uid,
)
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    inherit_segment_uid,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack.packJobUid import FaceGridAxis


def _axis_for_outward(outward: Facing) -> FaceGridAxis | None:
    dx, dy = GRID_OUTWARD_DELTA[outward]
    if dx != 0 and dy == 0:
        return FaceGridAxis.V
    if dy != 0 and dx == 0:
        return FaceGridAxis.H
    return None


def uid_for_front(
    front: FrontGeometry,
    *,
    world_uid: str,
    site_id: str,
    catalog: TileFaceCatalog | None,
    existing: dict[Coord, str],
    interior_seq: dict[tuple[int, int], int],
) -> str:
    inherited = inherit_segment_uid(front.corridor[:1] or front.rim, existing)
    if inherited:
        return inherited
    if catalog is not None and front.corridor:
        faces = catalog.faces_for_cells(front.corridor)
        if faces:
            uid = catalog.uid_for_faces(
                faces, axis=_axis_for_outward(front.outward),
            )
            if uid:
                return uid
        cx, cy = catalog.chunk_of(*min(front.corridor))
        k = interior_seq[(cx, cy)]
        interior_seq[(cx, cy)] = k + 1
        return catalog.interior_uid(cx, cy, k)
    return make_grade_uid(
        world_uid=world_uid, site_id=site_id, seed=min(front.rim),
    )
