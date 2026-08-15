"""R36w face catalog — preassigned grade uid from world_seed; job uid keys.

Chunk job uids of this tile are parents of a ``face_key`` (1 rim / 2 internal).
That count is clearance, not a tile→chunk job tree. Macro-tile uid is L0
(``full_bake``); this catalog only reads it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    make_seeded_uid,
)
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.pack.bake.macroTileUid import (
    macro_tile_uid as l0_macro_tile_uid,
    pack_job_seed,
)
from app.application.worldData.pack.refine.columnBounds import ColumnBounds
from app.application.worldData.pack.refine.detailedJobUid import (
    canonical_tile_edge,
    chunk_job_uid,
    face_grade_site,
    interior_grade_site,
    tile_edge_job_uid,
)
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.worldPack.packJobUid import FaceGridAxis, PackJobUid
from app.db.models.world import World

Coord = tuple[int, int]


@dataclass(frozen=True, slots=True, order=True)
class FaceKey:
    axis: FaceGridAxis
    cx: int
    cy: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "axis", FaceGridAxis(self.axis))

    def wire(self) -> str:
        return PackJobUid.canonical_defaults().face_wire(self.axis, self.cx, self.cy)

    def vertices(self) -> tuple[Coord, Coord]:
        """Chunk-grid vertices (SW origin of chunk indices)."""
        if self.axis == FaceGridAxis.V:
            return ((self.cx + 1, self.cy), (self.cx + 1, self.cy + 1))
        return ((self.cx, self.cy + 1), (self.cx + 1, self.cy + 1))


@dataclass(frozen=True, slots=True)
class TileFaceCatalog:
    """Unique chunk-grid faces + preassigned uids (R36w).

    Job keys are not a tile→chunk tree. Face parents = chunk uids on this tile.
    """

    world_seed: str
    tile_gx: int
    tile_gy: int
    origin_x: int
    origin_y: int
    tile_w: int
    tile_h: int
    chunk_size: int
    n_cx: int
    n_cy: int
    face_uids: dict[str, str]

    def chunk_of(self, x: int, y: int) -> tuple[int, int]:
        return (
            (x - self.origin_x) // self.chunk_size,
            (y - self.origin_y) // self.chunk_size,
        )

    def chunk_of_rect(self, rect: ColumnBounds) -> tuple[int, int]:
        return self.chunk_of(rect.x_min, rect.y_min)

    def uid_for_face(self, face: FaceKey) -> str:
        return self.face_uids[face.wire()]

    def is_internal_face(self, face: FaceKey) -> bool:
        """Shared by two chunks of this tile (not a macro-tile rim)."""
        if face.axis == FaceGridAxis.V:
            return 0 <= face.cx < self.n_cx - 1
        return 0 <= face.cy < self.n_cy - 1

    def is_tile_rim_face(self, face: FaceKey) -> bool:
        """East/west/north/south of this macro-tile (inter-tile catalog face)."""
        if face.axis == FaceGridAxis.V:
            return face.cx < 0 or face.cx == self.n_cx - 1
        return face.cy < 0 or face.cy == self.n_cy - 1

    def uid_for_faces(
        self,
        faces: tuple[FaceKey, ...] | list[FaceKey],
        *,
        axis: FaceGridAxis | str | None = None,
    ) -> str | None:
        """Bind a seed on several faces.

        1. Tile-rim on the sample axis (inter-tile owner-face occupancy).
        2. Any face on that axis (internal stitch; ignore incidental H/V rim).
        3. Any tile-rim, else min(face_key).
        """
        if not faces:
            return None
        unique = tuple(sorted(set(faces)))
        rim = tuple(f for f in unique if self.is_tile_rim_face(f))
        if axis is not None:
            axis = FaceGridAxis(axis)
        if axis in (FaceGridAxis.V, FaceGridAxis.H):
            rim_ax = tuple(f for f in rim if f.axis == axis)
            if rim_ax:
                return self.uid_for_face(min(rim_ax))
            ax = tuple(f for f in unique if f.axis == axis)
            if ax:
                return self.uid_for_face(min(ax))
        pick = rim or unique
        return self.uid_for_face(min(pick))

    def interior_uid(self, cx: int, cy: int, k: int) -> str:
        site = interior_grade_site(
            tile_gx=self.tile_gx, tile_gy=self.tile_gy, cx=cx, cy=cy, k=k,
        )
        return make_seeded_uid(world_seed=self.world_seed, site_id=site)

    def macro_tile_uid(self) -> str:
        """L0 tile uid — read, not minted by this catalog."""
        return l0_macro_tile_uid(
            world_seed=self.world_seed,
            tile_gx=self.tile_gx,
            tile_gy=self.tile_gy,
        )

    def job_uid_chunk(self, cx: int, cy: int) -> str:
        return chunk_job_uid(
            world_seed=self.world_seed,
            tile_gx=self.tile_gx,
            tile_gy=self.tile_gy,
            cx=cx,
            cy=cy,
        )

    def job_uid_tile_edge(self, side: str | Facing) -> str:
        return tile_edge_job_uid(
            world_seed=self.world_seed,
            tile_gx=self.tile_gx,
            tile_gy=self.tile_gy,
            side=side,
        )

    def owner_chunk(self, face: FaceKey) -> tuple[int, int]:
        if face.axis == FaceGridAxis.V:
            return (max(face.cx, 0), face.cy) if face.cx >= 0 else (0, face.cy)
        return (face.cx, max(face.cy, 0)) if face.cy >= 0 else (face.cx, 0)

    def is_owner_chunk(self, cx: int, cy: int, face: FaceKey) -> bool:
        return self.owner_chunk(face) == (cx, cy)

    def chunk_parents(self, face: FaceKey) -> tuple[tuple[int, int], ...]:
        """Chunks of this tile that share ``face``. Rim → 1; internal → 2."""
        if face.axis == FaceGridAxis.V:
            pair = ((face.cx, face.cy), (face.cx + 1, face.cy))
        else:
            pair = ((face.cx, face.cy), (face.cx, face.cy + 1))
        return tuple(
            c for c in pair
            if 0 <= c[0] < self.n_cx and 0 <= c[1] < self.n_cy
        )

    def chunk_parent_count(self, face: FaceKey) -> int:
        return len(self.chunk_parents(face))

    def chunk_parent_uids(self, face: FaceKey) -> tuple[str, ...]:
        return tuple(
            self.job_uid_chunk(cx, cy) for cx, cy in self.chunk_parents(face)
        )

    def face_for_outward(
        self,
        x: int,
        y: int,
        outward: tuple[int, int],
    ) -> FaceKey | None:
        """Catalog face crossed leaving ``(x, y)`` along ortho ``outward``."""
        cx, cy = self.chunk_of(x, y)
        if cx < 0 or cy < 0 or cx >= self.n_cx or cy >= self.n_cy:
            return None
        dx, dy = int(outward[0]), int(outward[1])
        x_min = self.origin_x + cx * self.chunk_size
        y_min = self.origin_y + cy * self.chunk_size
        x_max = min(x_min + self.chunk_size - 1, self.origin_x + self.tile_w - 1)
        y_max = min(y_min + self.chunk_size - 1, self.origin_y + self.tile_h - 1)
        if dx == 1 and x == x_max:
            return FaceKey(FaceGridAxis.V, cx, cy)
        if dx == -1 and x == x_min:
            return FaceKey(FaceGridAxis.V, cx - 1, cy)
        if dy == 1 and y == y_max:
            return FaceKey(FaceGridAxis.H, cx, cy)
        if dy == -1 and y == y_min:
            return FaceKey(FaceGridAxis.H, cx, cy - 1)
        return None

    def is_open_rim_step(
        self,
        last_free: Coord,
        outward: tuple[int, int],
    ) -> bool:
        """True when the step leaves a face with fewer than two chunk parents."""
        face = self.face_for_outward(last_free[0], last_free[1], outward)
        if face is None:
            return False
        return self.chunk_parent_count(face) < 2

    def faces_for_cell(self, x: int, y: int) -> tuple[FaceKey, ...]:
        cx, cy = self.chunk_of(x, y)
        if cx < 0 or cy < 0 or cx >= self.n_cx or cy >= self.n_cy:
            return ()
        x_min = self.origin_x + cx * self.chunk_size
        y_min = self.origin_y + cy * self.chunk_size
        x_max = min(x_min + self.chunk_size - 1, self.origin_x + self.tile_w - 1)
        y_max = min(y_min + self.chunk_size - 1, self.origin_y + self.tile_h - 1)
        found: list[FaceKey] = []
        if x == x_max:
            found.append(FaceKey(FaceGridAxis.V, cx, cy))
        if x == x_min:
            found.append(FaceKey(FaceGridAxis.V, cx - 1, cy))
        if y == y_max:
            found.append(FaceKey(FaceGridAxis.H, cx, cy))
        if y == y_min:
            found.append(FaceKey(FaceGridAxis.H, cx, cy - 1))
        return tuple(sorted(found))

    def faces_for_cells(self, cells: tuple[Coord, ...] | list[Coord]) -> tuple[FaceKey, ...]:
        found: set[FaceKey] = set()
        for x, y in cells:
            found.update(self.faces_for_cell(x, y))
        return tuple(sorted(found))

    def uid_for_cells(self, cells: tuple[Coord, ...], *, cx: int, cy: int) -> str:
        """Catalog face uid (min face_key) or interior|{k placeholder 0} — k set by caller."""
        faces = self.faces_for_cells(cells)
        if faces:
            uid = self.uid_for_faces(faces)
            if uid is not None:
                return uid
        return self.interior_uid(cx, cy, 0)


def seed_ref_axis(
    seeds: tuple[Coord, ...] | list[Coord],
    refs: set[Coord],
) -> FaceGridAxis | None:
    """Ortho seed↔ref axis (``V`` east-west, ``H`` north-south), or None."""
    axes: set[FaceGridAxis] = set()
    for sx, sy in seeds:
        for dx, dy in CARDINAL_WALL_OUTWARD_DELTA.values():
            if (sx + dx, sy + dy) in refs:
                axes.add(FaceGridAxis.V if dx != 0 else FaceGridAxis.H)
    if len(axes) == 1:
        return next(iter(axes))
    return None


def _owner_site(
    tile_gx: int,
    tile_gy: int,
    n_cx: int,
    n_cy: int,
    face: FaceKey,
) -> str:
    uid = PackJobUid.canonical_defaults()
    if face.axis == FaceGridAxis.V and face.cx < 0:
        owner_gx, owner_gy, _side = canonical_tile_edge(
            tile_gx, tile_gy, Facing.WEST,
        )
        return face_grade_site(
            owner_gx, owner_gy, uid.face_wire(FaceGridAxis.V, n_cx - 1, face.cy),
        )
    if face.axis == FaceGridAxis.H and face.cy < 0:
        owner_gx, owner_gy, _side = canonical_tile_edge(
            tile_gx, tile_gy, Facing.SOUTH,
        )
        return face_grade_site(
            owner_gx, owner_gy, uid.face_wire(FaceGridAxis.H, face.cx, n_cy - 1),
        )
    return face_grade_site(tile_gx, tile_gy, face.wire())


def build_tile_face_catalog(
    *,
    world_seed: str,
    tile_gx: int,
    tile_gy: int,
    origin_x: int,
    origin_y: int,
    tile_w: int,
    tile_h: int,
    chunk_size: int,
) -> TileFaceCatalog:
    n_cx = max(1, (max(1, tile_w) + chunk_size - 1) // chunk_size)
    n_cy = max(1, (max(1, tile_h) + chunk_size - 1) // chunk_size)
    face_uids: dict[str, str] = {}
    for cy in range(n_cy):
        for cx in range(-1, n_cx):
            face = FaceKey(FaceGridAxis.V, cx, cy)
            site = _owner_site(tile_gx, tile_gy, n_cx, n_cy, face)
            face_uids[face.wire()] = make_seeded_uid(
                world_seed=world_seed, site_id=site,
            )
    for cy in range(-1, n_cy):
        for cx in range(n_cx):
            face = FaceKey(FaceGridAxis.H, cx, cy)
            site = _owner_site(tile_gx, tile_gy, n_cx, n_cy, face)
            face_uids[face.wire()] = make_seeded_uid(
                world_seed=world_seed, site_id=site,
            )
    return TileFaceCatalog(
        world_seed=world_seed,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        origin_x=origin_x,
        origin_y=origin_y,
        tile_w=tile_w,
        tile_h=tile_h,
        chunk_size=chunk_size,
        n_cx=n_cx,
        n_cy=n_cy,
        face_uids=face_uids,
    )


def catalog_for_surface(
    world: World,
    bbox: ColumnBounds,
    *,
    tile_gx: int,
    tile_gy: int,
    chunk_size: int | None = None,
) -> TileFaceCatalog:
    size = chunk_size if chunk_size is not None else terrain_chunk_columns(world)
    return build_tile_face_catalog(
        world_seed=pack_job_seed(world),
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        origin_x=bbox.x_min,
        origin_y=bbox.y_min,
        tile_w=bbox.x_max - bbox.x_min + 1,
        tile_h=bbox.y_max - bbox.y_min + 1,
        chunk_size=size,
    )
