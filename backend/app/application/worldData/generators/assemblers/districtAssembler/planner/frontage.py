"""Frontage threads, touching street cells, alleys — C22 §5.1.3 / §5.5."""

from __future__ import annotations

import random
from collections import defaultdict

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
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
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.settlement.district.districtConnection import DistrictConnection
from app.dataModel.settlement.district.frontageTypeOrder import resolve_frontage_type_order
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

Coord = tuple[int, int]

_NEIGHBORS = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))

# TZ structure_type example: plaza skips frontage (tz_structure_connections.md §5.1.3).
PLAZA_STRUCTURE_TYPE = "plaza"


def is_plaza(template: dict) -> bool:
    st = template.get("structure_type") or template.get("system_type")
    return st == PLAZA_STRUCTURE_TYPE


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
    skeleton: CitySkeleton,
    known_types: frozenset[str],
    rng: random.Random,
    settlement_uid: str,
) -> list[str]:
    """Set AreaSlot.facing from abutting streets. Equal-rank tie-break on threads. Plaza skips."""
    district = slot.district_template.system_name
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
    for key, group in threads.items():
        cells: set[Coord] = set()
        types: list[str] = []
        for edge in group:
            cells |= edge_xy.get(edge.edge_uid, set())
            types.append(edge.connection_type)
        thread_xy[key] = cells
        thread_type[key] = types[0] if types else DistrictConnection.street_default().connection_type

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
                template=placement.template.get("system_name"),
                reason=PackingReason.PLAZA,
            )
            continue
        touching: list[tuple[tuple[str, int], str]] = []
        for key, xy in thread_xy.items():
            if edge_touches_plot(cells, xy):
                touching.append((key, thread_type[key]))
        if len(touching) < 2:
            continue
        ranked = sorted(touching, key=lambda item: _rank(item[1], order))
        best_rank = _rank(ranked[0][1], order)
        tied = [item for item in ranked if _rank(item[1], order) == best_rank]
        if len(tied) < 2:
            continue
        counts = [(thread_plot_count[k], k, ct) for k, ct in tied]
        counts.sort(key=lambda row: -row[0])
        if len(counts) >= 2 and counts[0][0] != counts[1][0]:
            winner = counts[0][1]
            packing_info(
                PackingStep.FRONTAGE, district=district,
                template=placement.template.get("system_name"),
                reason=PackingReason.THREAD_COUNT,
                counts={str(k): thread_plot_count[k] for k, _ct in tied},
            )
        else:
            seed = f"{settlement_uid}_{placement.building_x}_{placement.building_y}"
            local = random.Random(seed)
            winner = local.choice([k for k, _ct in tied])
            packing_info(
                PackingStep.FRONTAGE, district=district,
                template=placement.template.get("system_name"),
                reason=PackingReason.RNG,
                seed=seed,
            )
        placement.area_slot.facing = facing_from_street(list(cells), thread_xy[winner])
    _ = by_uid
    _ = rng
    return order


def alley_connection_type() -> str:
    return WorldConnectionTypeRegistry.require_engine("alley")


def alley_from_template(slot: DistrictSlot) -> str | None:
    want = alley_connection_type()
    for conn in slot.district_template.connections or []:
        if conn.connection_type == want:
            return want
    return None


def add_alleys(
    slot: DistrictSlot,
    placements: list[AreaPlacement],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    world_uid: str,
) -> None:
    """Alley thread only from DistrictConnection alley when ≥2 plots in a module and width fits."""
    district = slot.district_template.system_name
    alley_type = alley_from_template(slot)
    by_module: dict[tuple[int, int], list[AreaPlacement]] = defaultdict(list)
    for placement in placements:
        res = placement.reservation
        if res is None:
            continue
        by_module[(res.col, res.row)].append(placement)

    width = resolve_width(alley_connection_type())
    if width is None:
        packing_info(
            PackingStep.ALLEY, district=district,
            alley="no", reason=PackingReason.WIDTH,
        )
        return
    for (col, row), group in by_module.items():
        if alley_type is None:
            packing_info(
                PackingStep.ALLEY, district=district,
                n_plots=len(group), alley="no", reason=PackingReason.NOT_IN_SETTINGS,
            )
            continue
        if len(group) < 2:
            packing_info(
                PackingStep.ALLEY, district=district,
                n_plots=len(group), alley="no", reason=PackingReason.SINGLE_PLOT,
            )
            continue
        a, b = group[0], group[1]
        ax = a.building_x
        ay = a.building_y
        bx = b.building_x
        by = b.building_y
        gap = abs(bx - ax) if ay == by else abs(by - ay)
        if gap < width:
            packing_info(
                PackingStep.ALLEY, district=district,
                n_plots=len(group), alley="no", reason=PackingReason.WIDTH,
                width_cells=width,
            )
            continue
        from_node = _node_at(nodes, (ax + bx) // 2, ay if ay == by else (ay + by) // 2, world_uid)
        to_node = _node_at(
            nodes,
            (ax + bx) // 2 if ay == by else ax,
            (ay + by) // 2 if ay != by else ay,
            world_uid,
        )
        if from_node not in nodes:
            nodes.append(from_node)
        if to_node not in nodes:
            nodes.append(to_node)
        edges.append(ConnectionEdge(
            edge_uid=f"e_alley_{col}_{row}_{from_node.node_uid}",
            from_node_uid=from_node.node_uid,
            to_node_uid=to_node.node_uid,
            connection_type=alley_type,
            width_cells=width,
            has_sidewalk=False,
            graph_level=GraphLevel.DISTRICT.value,
            world_uid=world_uid,
        ))
        packing_info(
            PackingStep.ALLEY, district=district,
            n_plots=len(group), alley="yes", reason=PackingReason.FROM_CONNECTIONS,
            width_cells=width,
        )


def _node_at(
    existing: list[ConnectionNode],
    x: int,
    y: int,
    world_uid: str,
) -> ConnectionNode:
    for node in existing:
        if node.x == x and node.y == y:
            return node
    return ConnectionNode(
        node_uid=f"n_alley_{x}_{y}",
        x=x,
        y=y,
        z=0,
        node_type=ConnectionNodeType.INTERSECTION.value,
        graph_level=GraphLevel.DISTRICT.value,
        world_uid=world_uid,
    )


def outward_delta(facing: Facing) -> tuple[int, int]:
    return CARDINAL_WALL_OUTWARD_DELTA.get(
        facing, CARDINAL_WALL_OUTWARD_DELTA[Facing.SOUTH],
    )
