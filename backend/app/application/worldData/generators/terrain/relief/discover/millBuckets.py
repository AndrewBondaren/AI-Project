"""Q1 leftover/claimed and Q2 mill-event buckets — one cell, one bucket.

Keys are ``BucketRef`` (family + z + bake slot). Leftover slot is ``UNSET_SLOT``.
SoT: ``docs/tz_terrain_relief.md`` R41 T-18.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.application.worldData.generators.terrain.relief.discover.types import Coord

UNSET_SLOT = 0


class MillFamily(Enum):
    Q1 = "q1"
    Q2 = "q2"


class Q2Kind(Enum):
    LANDING = "landing"
    SIDE = "side"


Q2_DRAIN_ORDER = (Q2Kind.LANDING, Q2Kind.SIDE)


@dataclass(frozen=True, slots=True)
class BucketRef:
    """Queue identity. ``slot`` is the 1-based bake slot; leftover uses ``UNSET_SLOT``."""

    family: MillFamily
    z: int
    slot: int

    @classmethod
    def leftover(cls, z: int) -> BucketRef:
        return cls(MillFamily.Q1, int(z), UNSET_SLOT)

    @classmethod
    def claimed(cls, z: int, slot: int) -> BucketRef:
        return cls(MillFamily.Q1, int(z), int(slot))

    @classmethod
    def q2(cls, z_q1: int, slot: int) -> BucketRef:
        return cls(MillFamily.Q2, int(z_q1), int(slot))


class MillBuckets:
    """Q1 leftover + claimed, Q2 derivatives. Reverse index rejects duplicates."""

    def __init__(self) -> None:
        self.cell_to_bucket: dict[Coord, BucketRef] = {}
        self._cells: dict[BucketRef, dict[Coord, None]] = {}
        self._q2_kind: dict[Coord, Q2Kind] = {}

    def insert(
        self,
        ref: BucketRef,
        xy: Coord,
        *,
        kind: Q2Kind | None = None,
    ) -> bool:
        """False if ``xy`` is already in any bucket."""
        if xy in self.cell_to_bucket:
            return False
        if ref.family is MillFamily.Q2 and kind is None:
            raise ValueError("Q2 insert requires Q2Kind")
        self.cell_to_bucket[xy] = ref
        self._cells.setdefault(ref, {})[xy] = None
        if kind is not None:
            self._q2_kind[xy] = kind
        return True

    def move(
        self,
        ref: BucketRef,
        xy: Coord,
        *,
        kind: Q2Kind | None = None,
    ) -> bool:
        """Move ``xy`` to ``ref``. No-op True if already there."""
        if ref.family is MillFamily.Q2 and kind is None and xy not in self._q2_kind:
            raise ValueError("Q2 move requires Q2Kind")
        cur = self.cell_to_bucket.get(xy)
        if cur == ref:
            if kind is not None:
                self._q2_kind[xy] = kind
            return True
        if cur is None:
            return self.insert(ref, xy, kind=kind)
        bucket = self._cells.get(cur)
        if bucket is not None:
            bucket.pop(xy, None)
            if not bucket:
                self._cells.pop(cur, None)
        self._q2_kind.pop(xy, None)
        self.cell_to_bucket[xy] = ref
        self._cells.setdefault(ref, {})[xy] = None
        if kind is not None:
            self._q2_kind[xy] = kind
        return True

    def discard(self, xy: Coord) -> None:
        cur = self.cell_to_bucket.pop(xy, None)
        if cur is None:
            return
        bucket = self._cells.get(cur)
        if bucket is not None:
            bucket.pop(xy, None)
            if not bucket:
                self._cells.pop(cur, None)
        self._q2_kind.pop(xy, None)

    def leftover_z(self, z: int) -> tuple[Coord, ...]:
        bucket = self._cells.get(BucketRef.leftover(z))
        if not bucket:
            return ()
        return tuple(bucket)

    def max_leftover_z(self) -> int | None:
        best: int | None = None
        for ref, cells in self._cells.items():
            if ref.family is not MillFamily.Q1 or ref.slot != UNSET_SLOT or not cells:
                continue
            if best is None or ref.z > best:
                best = ref.z
        return best

    def drop_leftover_z(self, z: int) -> None:
        for xy in self.leftover_z(z):
            self.discard(xy)

    def q2_for(self, z_q1: int, kind: Q2Kind | None = None) -> tuple[Coord, ...]:
        z_q1 = int(z_q1)
        out: list[Coord] = []
        for ref, cells in self._cells.items():
            if ref.family is not MillFamily.Q2 or ref.z != z_q1:
                continue
            for xy in cells:
                if kind is None or self._q2_kind.get(xy) is kind:
                    out.append(xy)
        return tuple(out)

    def q2_kind(self, xy: Coord) -> Q2Kind | None:
        return self._q2_kind.get(xy)

    def is_leftover(self, xy: Coord, z: int) -> bool:
        return self.cell_to_bucket.get(xy) == BucketRef.leftover(z)
