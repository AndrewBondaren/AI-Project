"""Application bake types for relief pipeline v2 — C38 / C40.

Not persist-POJO. Do not add ``occ`` / slot / front fields to
``ReliefGradeInstance`` / ``ReliefGradeSystem``.
SoT: ``docs/tz_terrain_relief.md`` R41.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefContext

Coord = tuple[int, int]

# occ/seam: FREE_MARK free; negative = foreign (existing uid / other chunk).
FREE_MARK = 0
FOREIGN_MARK = -1


class ReliefSurface(Protocol):
    """Read-only height/terrain for discover. ``MeterGradeSurface`` satisfies this."""

    def z_at(self, xy: Coord) -> int | None: ...
    def terrain_at(self, xy: Coord) -> str | None: ...
    def hydro_role_at(self, xy: Coord) -> HydrologyCellRole | None: ...
    def hydro_at(self, xy: Coord) -> MapCellHydrology | None: ...


def cell_z(surface: ReliefSurface, xy: Coord) -> int | None:
    z = surface.z_at(xy)
    return None if z is None else int(z)


CellBlocked = Callable[[Coord], bool]
# Length-only cap before C41 (R41-T-3). None = skip this trace. No pick.
CapFront = Callable[[ReliefContext], int | None]


@dataclass(frozen=True, slots=True)
class GradePaintSpec:
    """Sole L2 paint input for one front (C40). Knobs live on ``decision``."""

    grade_uid: str
    outward: Facing
    front_w: int
    anchor_top: Coord
    anchor_bottom: Coord
    decision: RibbonGradeDecision
    corridor: tuple[Coord, ...]


@dataclass(slots=True)
class ReliefVertices:
    """Bake index: slots / occupancy / ray-seam / facing claims. Local ``lx,ly``."""

    origin_x: int
    origin_y: int
    width: int
    height: int
    at_grid: array
    occ: array
    seam: array
    facing_bits: array
    members: list[dict[Coord, int]] = field(default_factory=list)
    uids: list[str] = field(default_factory=list)
    q3_parent: dict[int, int] = field(default_factory=dict)

    @classmethod
    def for_bounds(
        cls,
        *,
        origin_x: int,
        origin_y: int,
        width: int,
        height: int,
    ) -> ReliefVertices:
        n = max(0, int(width) * int(height))
        zeros = array("i", [0]) * n
        return cls(
            origin_x=int(origin_x),
            origin_y=int(origin_y),
            width=int(width),
            height=int(height),
            at_grid=array("i", zeros),
            occ=array("i", zeros),
            seam=array("i", zeros),
            facing_bits=array("B", [0]) * n,
        )

    def index(self, x: int, y: int) -> int | None:
        lx = int(x) - self.origin_x
        ly = int(y) - self.origin_y
        if lx < 0 or ly < 0 or lx >= self.width or ly >= self.height:
            return None
        return ly * self.width + lx

    def add_vertex(self, body: Mapping[Coord, int]) -> int:
        """Append a slot (1-based in ``at_grid``). ``uids`` stay empty until T-3c."""
        slot = len(self.members) + 1
        members = dict(body)
        self.members.append(members)
        self.uids.append("")
        for (x, y) in members:
            i = self.index(x, y)
            if i is not None:
                self.at_grid[i] = slot
        return slot

    def mark_occ(self, xy: Coord, slot: int) -> None:
        i = self.index(xy[0], xy[1])
        if i is not None:
            self.occ[i] = int(slot)

    def mark_seam(self, xy: Coord, slot: int) -> None:
        i = self.index(xy[0], xy[1])
        if i is not None:
            self.seam[i] = int(slot)

    def mark_foreign(self, xy: Coord) -> None:
        """Existing corridor (other chunk / prior uid) — not a slot of this rect."""
        i = self.index(xy[0], xy[1])
        if i is not None and self.occ[i] == FREE_MARK:
            self.occ[i] = FOREIGN_MARK

    def claim_facings(self, cells: Sequence[Coord], facing: Facing) -> bool:
        """Claim ``facing`` on each cell. False if that facing is already taken."""
        from app.application.worldData.generators.terrain.relief.discover.neighbors import (
            FACING_BIT,
        )

        bit = FACING_BIT[facing]
        idxs: list[int] = []
        for xy in cells:
            i = self.index(xy[0], xy[1])
            if i is None:
                continue
            if self.facing_bits[i] & bit:
                return False
            idxs.append(i)
        for i in idxs:
            self.facing_bits[i] |= bit
        return True

    def facing_count(self, xy: Coord) -> int:
        i = self.index(xy[0], xy[1])
        if i is None:
            return 0
        return int(self.facing_bits[i]).bit_count()

    def is_free(self, xy: Coord) -> bool:
        i = self.index(xy[0], xy[1])
        if i is None:
            return False
        return (
            self.occ[i] == FREE_MARK
            and self.at_grid[i] == FREE_MARK
            and self.seam[i] == FREE_MARK
        )


@dataclass(frozen=True, slots=True)
class ProposedTrace:
    """C41 input: one lockstep trace before seam/occ."""

    slot: int
    z_body: int
    rim: tuple[Coord, ...]
    facing: Facing
    first_dz: int
    trace: tuple[Coord, ...]
    z_end: int


@dataclass(frozen=True, slots=True)
class FrontGeometry:
    """One lockstep front after C41, before L2 paint.

    ``path_length`` / ``z_end`` are the C41 corridor span (R41-T-8): classify
    and stamp share this L, not the pre-seam walk.
    """

    slot: int
    context: ReliefContext
    outward: Facing
    first_dz: int
    z_body: int
    z_end: int
    path_length: int
    rim: tuple[Coord, ...]
    trace: tuple[Coord, ...]
    corridor: tuple[Coord, ...]
    anchor_bottom: Coord
    hit_seam: bool


@dataclass(frozen=True, slots=True)
class DiscoveredFront:
    """Worker object: C40 spec plus identity the persist layer needs."""

    spec: GradePaintSpec
    context: ReliefContext
    site_id: str
    slot: int
    template_uid: str | None
    rim: tuple[Coord, ...]
    terrain_key: str
    system_terrain: str
    dz: int
    owner_uid: str | None = None
