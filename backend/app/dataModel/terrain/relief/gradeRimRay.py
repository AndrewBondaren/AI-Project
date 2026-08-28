"""Mill leftover ``GradeRimRay`` (C41 sender) + locked-test leftover pack helpers.

Sidecar wire is ``GradeCellSlots`` / ``SCH-GRADE-CELL-SLOTS``, not ``rays[]``.
``downhill_leftover_rim_rays`` / ``couple_rim_rays`` / ``pack_rim_slot_rays`` are
locked-test leftover pack — not FineChunkPersist.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA, opposite
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes


class GradeRimRay(BaseModel):
    """One pack slot: sender C41 leftover or derived receiver (world XY)."""

    SCHEMA_ID: ClassVar[str] = "SCH-GRADE-RIM-RAY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: int
    y: int
    facing: Facing
    kind: ReliefSideKind = Field(
        default=ReliefSideKind.SLOPE,
        description="Pack slot: SLOPE/SHEER leftover or COUPLE. Instance kind is SLOPE/SHEER only.",
    )

    @property
    def cell(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))


def merge_grade_rim_rays(*groups: Iterable[GradeRimRay]) -> tuple[GradeRimRay, ...]:
    """First-wins on ``(x, y, facing)`` — occupied slots are not overwritten."""
    by_key: dict[tuple[int, int, Facing], GradeRimRay] = {}
    for group in groups:
        for ray in group:
            key = (int(ray.x), int(ray.y), ray.facing)
            if key not in by_key:
                by_key[key] = ray
    return tuple(by_key.values())


def receiver_rim_ray(sender: GradeRimRay) -> GradeRimRay:
    """Hit cell + ``opposite`` facing; same kind. Not a second C41 claim."""
    dx, dy = GRID_OUTWARD_DELTA[sender.facing]
    return GradeRimRay(
        x=int(sender.x) + int(dx),
        y=int(sender.y) + int(dy),
        facing=opposite(sender.facing),
        kind=sender.kind,
    )


def unified_surface_facings(
    xy: tuple[int, int],
    z_height_map: Mapping[tuple[int, int], int],
) -> frozenset[Facing]:
    """Facings whose neighbor exists in ``z_height_map`` at the same surface z (coupling)."""
    x, y = int(xy[0]), int(xy[1])
    z = z_height_map.get((x, y))
    if z is None:
        return frozenset()
    z = int(z)
    out: list[Facing] = []
    for facing in Facing:
        dx, dy = GRID_OUTWARD_DELTA[facing]
        nb = (x + dx, y + dy)
        zn = z_height_map.get(nb)
        if zn is not None and int(zn) == z:
            out.append(facing)
    return frozenset(out)


def pack_rim_slot_rays(
    senders: Iterable[GradeRimRay],
    *,
    cells: Collection[tuple[int, int]],
) -> tuple[GradeRimRay, ...]:
    """Sender slots plus receivers whose cell exists in this bake (TZ omit)."""
    allowed = {(int(x), int(y)) for x, y in cells}
    out: list[GradeRimRay] = []
    for sender in senders:
        out.append(sender)
        recv = receiver_rim_ray(sender)
        if recv.cell in allowed:
            out.append(recv)
    return merge_grade_rim_rays(out)


def leftover_pack_kind(kind: ReliefSideKind) -> bool:
    """SLOPE/SHEER leftover. COUPLE is coupling, not a C41 leftover ray."""
    return kind is ReliefSideKind.SLOPE or kind is ReliefSideKind.SHEER


def _downhill_leftover_kind(abs_dz: int) -> ReliefSideKind | None:
    env = ReliefOntologyEnvelopes.canonical_defaults().plains
    if not env.stamps_first_step(abs_dz, ReliefContext.OPEN_LAND):
        return None
    outcome = env.slope_outcome(abs_dz, 1)
    if outcome == "slope":
        return ReliefSideKind.SLOPE
    if outcome == "sheer":
        return ReliefSideKind.SHEER
    return None


def downhill_leftover_rim_rays(
    leftover: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
) -> tuple[GradeRimRay, ...]:
    """SLOPE/SHEER on empty downhill facings of leftover origins (both ends).

    Mill may skip a diagonal *front* when an ortho run already covers the
    landing. Pack still needs that Facing when the neighbor is in
    ``z_height_map``. Same-z is COUPLE. Halo-only plains are not origins.
    """
    occupied: set[tuple[int, int, Facing]] = set()
    origins: set[tuple[int, int]] = set()
    for ray in leftover:
        occupied.add((int(ray.x), int(ray.y), ray.facing))
        if leftover_pack_kind(ray.kind):
            origins.add(ray.cell)
    seen: set[tuple[int, int, Facing]] = set()
    out: list[GradeRimRay] = []
    for cell in origins:
        z = z_height_map.get(cell)
        if z is None:
            continue
        for facing in Facing:
            key = (cell[0], cell[1], facing)
            if key in occupied or key in seen:
                continue
            dx, dy = GRID_OUTWARD_DELTA[facing]
            nb = (cell[0] + dx, cell[1] + dy)
            zn = z_height_map.get(nb)
            if zn is None or int(zn) >= int(z):
                continue
            kind = _downhill_leftover_kind(int(z) - int(zn))
            if kind is None:
                continue
            seen.add(key)
            out.append(
                GradeRimRay(x=cell[0], y=cell[1], facing=facing, kind=kind),
            )
            opp = opposite(facing)
            nkey = (nb[0], nb[1], opp)
            if nkey in occupied or nkey in seen:
                continue
            seen.add(nkey)
            out.append(
                GradeRimRay(x=nb[0], y=nb[1], facing=opp, kind=kind),
            )
    return tuple(out)


def couple_rim_rays(
    cells: Iterable[tuple[int, int]],
    leftover: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
) -> tuple[GradeRimRay, ...]:
    """COUPLE both ends for same-z neighbors of leftover + 8-halo cells.

    Empty leftover slots only. Neighbor missing from ``z_height_map`` omits
    that end. Does not invent SLOPE/SHEER. Does not grow leftover_plus_halo
    (COUPLE kind is ignored there).
    """
    occupied: set[tuple[int, int, Facing]] = set()
    for ray in leftover:
        occupied.add((int(ray.x), int(ray.y), ray.facing))
    seen: set[tuple[int, int, Facing]] = set()
    out: list[GradeRimRay] = []
    for xy in cells:
        cell = (int(xy[0]), int(xy[1]))
        for facing in unified_surface_facings(cell, z_height_map):
            key = (cell[0], cell[1], facing)
            if key in occupied or key in seen:
                continue
            seen.add(key)
            out.append(
                GradeRimRay(
                    x=cell[0], y=cell[1], facing=facing, kind=ReliefSideKind.COUPLE,
                ),
            )
            dx, dy = GRID_OUTWARD_DELTA[facing]
            nb = (cell[0] + dx, cell[1] + dy)
            if nb not in z_height_map:
                continue
            opp = opposite(facing)
            nkey = (nb[0], nb[1], opp)
            if nkey in occupied or nkey in seen:
                continue
            seen.add(nkey)
            out.append(
                GradeRimRay(
                    x=nb[0], y=nb[1], facing=opp, kind=ReliefSideKind.COUPLE,
                ),
            )
    return tuple(out)
