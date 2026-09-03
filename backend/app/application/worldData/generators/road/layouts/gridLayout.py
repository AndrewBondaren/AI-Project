"""
Grid street layout — lattice step from DistrictDensity, omit edges through pass-1 reservations.
"""
from __future__ import annotations

import random
import uuid

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import (
    ConnectionEntry,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.geometry import (
    axis_lines,
    district_step,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    StreetFrameContext,
)
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
from app.dataModel.spatial.facing import Facing, is_latitudinal_edge, is_meridional_edge
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

_AUTO_SIDEWALK_TYPES = {"road", "highway"}


def generate_grid(
    slot:            DistrictSlot,
    skeleton:        CitySkeleton,
    world_uid:       str,
    connection_type: str,
    lanes_per_side:  int,
    has_sidewalk:    bool,
    rng:             random.Random,
    surface:         dict[tuple[int, int], int] | None = None,
    frame:           StreetFrameContext | None = None,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    _ = rng
    pin_z = slot.ground_z
    z_lookup = surface or {}

    def node_z(x: int, y: int) -> int:
        return int(z_lookup.get((x, y), pin_z))

    if frame is not None:
        inner = frame.inner
        step = frame.step
        blocked = frame.blocked_rects
    else:
        inner = InnerBBox(
            slot.origin_x, slot.origin_y,
            slot.origin_x + slot.width_m, slot.origin_y + slot.depth_m,
        )
        step = district_step(slot, skeleton)
        blocked = ()

    if inner.empty:
        return [], []

    xs = axis_lines(inner.x0, inner.x1, step)
    ys = axis_lines(inner.y0, inner.y1, step)
    if len(xs) < 2 or len(ys) < 2:
        return [], []

    width = resolve_width(connection_type, lanes_per_side, bidirectional=True)
    node_grid: dict[tuple[int, int], ConnectionNode] = {}

    def get_or_create(col: int, row: int) -> ConnectionNode:
        key = (col, row)
        if key not in node_grid:
            x = xs[col]
            y = ys[row]
            z = node_z(x, y)
            node_grid[key] = ConnectionNode(
                node_uid=f"n_{x}_{y}_{z}_{uuid.uuid4().hex[:6]}",
                x=x, y=y, z=z,
                node_type=ConnectionNodeType.INTERSECTION.value,
                graph_level=GraphLevel.DISTRICT.value,
                world_uid=world_uid,
            )
        return node_grid[key]

    for col in range(len(xs)):
        for row in range(len(ys)):
            get_or_create(col, row)

    edges: list[ConnectionEdge] = []
    edge_keys: set[frozenset[str]] = set()

    def make_edge(a: ConnectionNode, b: ConnectionNode, conn_type: str | None = None) -> ConnectionEdge:
        return ConnectionEdge(
            edge_uid=f"e_{a.node_uid}_{b.node_uid}",
            from_node_uid=a.node_uid,
            to_node_uid=b.node_uid,
            connection_type=conn_type or connection_type,
            bidirectional=True,
            lanes_per_side=lanes_per_side,
            width_cells=width if conn_type is None else resolve_width(
                conn_type, lanes_per_side, True,
            ),
            has_sidewalk=has_sidewalk,
            graph_level=GraphLevel.DISTRICT.value,
            world_uid=world_uid,
        )

    def ensure_edge(a: ConnectionNode, b: ConnectionNode, conn_type: str | None = None) -> None:
        key = frozenset((a.node_uid, b.node_uid))
        if key in edge_keys:
            if conn_type is not None:
                for edge in edges:
                    ids = frozenset((edge.from_node_uid, edge.to_node_uid))
                    if ids == key:
                        edge.connection_type = conn_type
                        extra_w = resolve_width(conn_type, lanes_per_side, True)
                        if extra_w is not None:
                            edge.width_cells = extra_w
            return
        edge_keys.add(key)
        edges.append(make_edge(a, b, conn_type))

    def omits_horizontal(y: int, x0: int, x1: int) -> bool:
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        for rx0, ry0, rx1, ry1 in blocked:
            if lo < rx1 and hi > rx0 and ry0 < y < ry1:
                return True
        return False

    def omits_vertical(x: int, y0: int, y1: int) -> bool:
        lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
        for rx0, ry0, rx1, ry1 in blocked:
            if lo < ry1 and hi > ry0 and rx0 < x < rx1:
                return True
        return False

    for row, y in enumerate(ys):
        for col in range(len(xs) - 1):
            a = get_or_create(col, row)
            b = get_or_create(col + 1, row)
            if omits_horizontal(y, a.x, b.x):
                continue
            ensure_edge(a, b)

    for col, x in enumerate(xs):
        for row in range(len(ys) - 1):
            a = get_or_create(col, row)
            b = get_or_create(col, row + 1)
            if omits_vertical(x, a.y, b.y):
                continue
            ensure_edge(a, b)

    extra_nodes: list[ConnectionNode] = []
    _apply_through_threads(
        slot.entry_nodes, node_grid, ensure_edge, xs, ys,
        omits_horizontal, omits_vertical,
    )
    extra_nodes.extend(_connect_entry_points(
        slot.entry_nodes, node_grid, ensure_edge, xs, ys,
    ))
    _ = _AUTO_SIDEWALK_TYPES
    nodes = list(node_grid.values())
    seen = {n.node_uid for n in nodes}
    for node in extra_nodes:
        if node.node_uid not in seen:
            nodes.append(node)
            seen.add(node.node_uid)
    return nodes, edges


def _nearest_index(lines: list[int], value: int) -> int:
    return min(range(len(lines)), key=lambda i: abs(lines[i] - value))


def _snap_entry(
    entry: ConnectionEntry,
    xs: list[int],
    ys: list[int],
) -> tuple[int, int]:
    facing = entry.facing
    if is_meridional_edge(facing):
        col = _nearest_index(xs, entry.node.x)
        row = 0 if facing == Facing.SOUTH else len(ys) - 1
        return col, row
    if is_latitudinal_edge(facing):
        col = len(xs) - 1 if facing == Facing.EAST else 0
        row = _nearest_index(ys, entry.node.y)
        return col, row
    col = _nearest_index(xs, entry.node.x)
    row = _nearest_index(ys, entry.node.y)
    return col, row


def _apply_through_threads(
    entry_nodes: list[ConnectionEntry],
    node_grid: dict[tuple[int, int], ConnectionNode],
    ensure_edge,
    xs: list[int],
    ys: list[int],
    omits_horizontal,
    omits_vertical,
) -> None:
    through_map = {
        e.node.node_uid: e
        for e in entry_nodes
        if e.role == DistrictEntryRole.THROUGH_ROAD and e.paired_exit_uid is not None
    }
    processed: set[frozenset[str]] = set()
    for entry in entry_nodes:
        if entry.role != DistrictEntryRole.THROUGH_ROAD or entry.paired_exit_uid is None:
            continue
        pair = frozenset((entry.node.node_uid, entry.paired_exit_uid))
        if pair in processed:
            continue
        processed.add(pair)
        exit_entry = through_map.get(entry.paired_exit_uid)
        if exit_entry is None:
            continue
        c0, r0 = _snap_entry(entry, xs, ys)
        c1, r1 = _snap_entry(exit_entry, xs, ys)
        conn = entry.connection_type
        if r0 == r1:
            lo, hi = (c0, c1) if c0 <= c1 else (c1, c0)
            for col in range(lo, hi):
                a = node_grid.get((col, r0))
                b = node_grid.get((col + 1, r0))
                if a is None or b is None:
                    continue
                if omits_horizontal(a.y, a.x, b.x):
                    continue
                ensure_edge(a, b, conn)
        elif c0 == c1:
            lo, hi = (r0, r1) if r0 <= r1 else (r1, r0)
            for row in range(lo, hi):
                a = node_grid.get((c0, row))
                b = node_grid.get((c0, row + 1))
                if a is None or b is None:
                    continue
                if omits_vertical(a.x, a.y, b.y):
                    continue
                ensure_edge(a, b, conn)


def _connect_entry_points(
    entry_nodes: list[ConnectionEntry],
    node_grid: dict[tuple[int, int], ConnectionNode],
    ensure_edge,
    xs: list[int],
    ys: list[int],
) -> list[ConnectionNode]:
    extra: list[ConnectionNode] = []
    for entry in entry_nodes:
        if entry.role != DistrictEntryRole.ENTRY_POINT:
            continue
        col, row = _snap_entry(entry, xs, ys)
        grid = node_grid.get((col, row))
        if grid is None:
            continue
        node = entry.node
        extra.append(node)
        if (node.x, node.y) == (grid.x, grid.y):
            continue
        ensure_edge(node, grid)
    return extra
