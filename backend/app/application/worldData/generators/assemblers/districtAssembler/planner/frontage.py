"""Frontage threads, touching street cells — C22 §5.1.3 / §5.5."""

from __future__ import annotations

import random
from collections import defaultdict

from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    AreaPlacement,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_info,
)
from app.dataModel.locations.settlement.district.districtConnection import (
    DistrictConnection,
)
from app.dataModel.locations.settlement.enums.districtStreetRole import (
    DistrictStreetRole,
    frontage_role_rank,
)
from app.dataModel.locations.settlement.district.frontageTypeOrder import resolve_frontage_type_order
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurposeFamily
from app.ids import UidKind, entity_rng
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

Coord = tuple[int, int]

_NEIGHBORS = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))

def is_plaza(template: PlotLayoutTemplate) -> bool:
    """Public plots skip frontage hierarchy, including plots with a building."""
    return template.plot_type == BuildingPurposeFamily.PUBLIC


def plot_cells(placement: AreaPlacement) -> set[Coord]:
    return set(placement.area_slot.cells)


def touching_street_xy(cells: set[Coord], street_xy: set[Coord]) -> set[Coord]:
    out: set[Coord] = set()
    for x, y in cells:
        for dx, dy in _NEIGHBORS:
            t = (x + dx, y + dy)
            if t in street_xy:
                out.add(t)
    return out


def edge_touches_plot(plot: set[Coord], edge_xy: set[Coord]) -> bool:
    return bool(touching_street_xy(plot, edge_xy))


def facing_from_street(cells: list[Coord], street_xy: set[Coord]) -> Facing:
    if not cells or not street_xy:
        return Facing.SOUTH
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    scores: dict[Facing, int] = {
        Facing.WEST: 0, Facing.EAST: 0, Facing.SOUTH: 0, Facing.NORTH: 0,
    }
    cell_set = set(cells)
    for x, y in cell_set:
        if x == x0:
            scores[Facing.WEST] += 1 if (x - 1, y) in street_xy or (x, y) in street_xy else 0
        if x == x1:
            scores[Facing.EAST] += 1 if (x + 1, y) in street_xy or (x, y) in street_xy else 0
        if y == y0:
            scores[Facing.SOUTH] += 1 if (x, y - 1) in street_xy or (x, y) in street_xy else 0
        if y == y1:
            scores[Facing.NORTH] += 1 if (x, y + 1) in street_xy or (x, y) in street_xy else 0
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        return Facing.SOUTH
    return best[0]


def _thread_key(a: ConnectionNode, b: ConnectionNode) -> tuple[str, int]:
    if a.y == b.y:
        return ("h", a.y)
    if a.x == b.x:
        return ("v", a.x)
    return ("d", a.x + b.x + a.y + b.y)


def stitch_threads(
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> dict[tuple[str, int], list[ConnectionEdge]]:
    by_uid = {n.node_uid: n for n in nodes}
    groups: dict[tuple[str, int], list[ConnectionEdge]] = defaultdict(list)
    for edge in edges:
        a = by_uid.get(edge.from_node_uid)
        b = by_uid.get(edge.to_node_uid)
        if a is None or b is None:
            continue
        groups[_thread_key(a, b)].append(edge)
    return groups


def _rank(connection_type: str, order: list[str]) -> int:
    try:
        return order.index(connection_type)
    except ValueError:
        return len(order)


def apply_frontage(
    placements: list[AreaPlacement],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    edge_xy: dict[str, set[Coord]],
    street_xy: set[Coord],
    slot: DistrictSlot,
    skeleton: SettlementSkeleton,
    known_types: frozenset[str],
    rng: random.Random,
    settlement_uid: str,
    world_uid: str,
    edge_roles: dict[str, DistrictStreetRole] | None = None,
) -> list[str]:
    """Set AreaSlot.facing from abutting streets. Type then role; equal-rank tie-break."""
    district = slot.district_template.system_name
    roles = edge_roles or {}
    order, skipped = resolve_frontage_type_order(
        slot.district_template.frontage_type_order,
        skeleton.frontage_type_order,
        known_types,
    )
    for key in skipped:
        packing_info(
            PackingStep.FRONTAGE, district=district,
            reason=PackingReason.SKIP_UNKNOWN, connection_type=key,
        )

    threads = stitch_threads(nodes, edges)
    by_uid = {n.node_uid: n for n in nodes}
    thread_xy: dict[tuple[str, int], set[Coord]] = {}
    thread_type: dict[tuple[str, int], str] = {}
    thread_role: dict[tuple[str, int], DistrictStreetRole | None] = {}
    for key, group in threads.items():
        cells: set[Coord] = set()
        types: list[str] = []
        group_roles: list[DistrictStreetRole | None] = []
        for edge in group:
            cells |= edge_xy.get(edge.edge_uid, set())
            types.append(edge.connection_type)
            group_roles.append(roles.get(edge.edge_uid))
        thread_xy[key] = cells
        thread_type[key] = types[0] if types else DistrictConnection.street_default().connection_type
        named = [r for r in group_roles if r is not None]
        thread_role[key] = (
            min(named, key=lambda r: r.frontage_rank()) if named else None
        )

    plot_sets = [plot_cells(p) for p in placements]
    thread_plot_count: dict[tuple[str, int], int] = {
        key: sum(1 for cells in plot_sets if edge_touches_plot(cells, xy))
        for key, xy in thread_xy.items()
    }

    for placement, cells in zip(placements, plot_sets):
        placement.area_slot.facing = facing_from_street(list(cells), street_xy)
        if is_plaza(placement.template):
            packing_info(
                PackingStep.FRONTAGE, district=district,
                template=placement.template.system_name,
                reason=PackingReason.PLAZA,
            )
            continue
        touching: list[tuple[tuple[str, int], str]] = []
        for key, xy in thread_xy.items():
            if edge_touches_plot(cells, xy):
                touching.append((key, thread_type[key]))
        if len(touching) < 2:
            continue

        def _frontage_key(item: tuple[tuple[str, int], str]) -> tuple[int, int]:
            thread_key, conn_type = item
            return (
                _rank(conn_type, order),
                frontage_role_rank(thread_role.get(thread_key)),
            )

        ranked = sorted(touching, key=_frontage_key)
        best = _frontage_key(ranked[0])
        tied = [item for item in ranked if _frontage_key(item) == best]
        if len(tied) == 1:
            winner = tied[0][0]
            placement.area_slot.facing = facing_from_street(list(cells), thread_xy[winner])
            continue
        counts = [(thread_plot_count[k], k, ct) for k, ct in tied]
        counts.sort(key=lambda row: -row[0])
        if len(counts) >= 2 and counts[0][0] != counts[1][0]:
            winner = counts[0][1]
            packing_info(
                PackingStep.FRONTAGE, district=district,
                template=placement.template.system_name,
                reason=PackingReason.THREAD_COUNT,
                counts={str(k): thread_plot_count[k] for k, _ct in tied},
            )
        else:
            local = entity_rng(
                world_uid, UidKind.FRONTAGE,
                settlement=settlement_uid,
                x=placement.building_x, y=placement.building_y,
            )
            winner = local.choice([k for k, _ct in tied])
            packing_info(
                PackingStep.FRONTAGE, district=district,
                template=placement.template.system_name,
                reason=PackingReason.RNG,
            )
        placement.area_slot.facing = facing_from_street(list(cells), thread_xy[winner])
    _ = by_uid
    _ = rng
    return order


def outward_delta(facing: Facing) -> tuple[int, int]:
    return CARDINAL_WALL_OUTWARD_DELTA.get(
        facing, CARDINAL_WALL_OUTWARD_DELTA[Facing.SOUTH],
    )
