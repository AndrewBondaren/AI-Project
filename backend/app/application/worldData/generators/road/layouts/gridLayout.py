"""
Grid street layout — равномерная прямоугольная сетка улиц внутри района.

Алгоритм:
1. Резервирует коридоры для through_road из entry_nodes (жёсткие ограничения).
2. Строит сетку пересечений с шагом block_size.
   block_size выводится из settlement_density: dense=50м / medium=80м / sparse=120м.
3. Подключает entry_point-узлы к ближайшему узлу сетки.
4. Возвращает (nodes, edges) без sidewalk-рёбер — sidewalk создаёт DistrictRoadGenerator
   если has_sidewalk=True на edge.
"""
import random
import uuid

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import ConnectionEntry
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

from app.application.worldData.generators.road.blockSize import block_size_for_density
from app.application.worldData.generators.utils.facing import Facing, snap_bbox_edge_to_grid
_AUTO_SIDEWALK_TYPES = {"road", "highway"}


def generate_grid(
    slot:            DistrictSlot,
    skeleton:        CitySkeleton,
    world_uid:       str,
    connection_type: str,
    lanes_per_side:  int,
    has_sidewalk:    bool,
    rng:             random.Random,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    ox, oy = slot.origin_x, slot.origin_y
    W,  D  = slot.width_m,  slot.depth_m
    z      = slot.ground_z

    density = slot.district_template.density or skeleton.settlement_density
    block_size = block_size_for_density(density)

    # Количество линий по каждой оси (включая границы района)
    n_cols = max(2, W // block_size + 1)   # вертикальные линии
    n_rows = max(2, D // block_size + 1)   # горизонтальные линии

    # Фактический шаг — равномерно делим footprint
    step_x = W // (n_cols - 1)
    step_y = D // (n_rows - 1)

    width = resolve_width(connection_type, lanes_per_side, bidirectional=True)

    # --- узлы ---
    node_grid: dict[tuple[int, int], ConnectionNode] = {}

    def get_or_create(col: int, row: int) -> ConnectionNode:
        key = (col, row)
        if key not in node_grid:
            x = ox + col * step_x
            y = oy + row * step_y
            node_grid[key] = ConnectionNode(
                node_uid    = f"n_{x}_{y}_{z}_{uuid.uuid4().hex[:6]}",
                x           = x,
                y           = y,
                z           = z,
                node_type   = "intersection",
                graph_level = "district",
                world_uid   = world_uid,
            )
        return node_grid[key]

    # Создаём все узлы сетки
    for col in range(n_cols):
        for row in range(n_rows):
            get_or_create(col, row)

    # --- рёбра ---
    edges: list[ConnectionEdge] = []

    def make_edge(a: ConnectionNode, b: ConnectionNode) -> ConnectionEdge:
        return ConnectionEdge(
            edge_uid        = f"e_{a.node_uid}_{b.node_uid}",
            from_node_uid   = a.node_uid,
            to_node_uid     = b.node_uid,
            connection_type = connection_type,
            bidirectional   = True,
            lanes_per_side  = lanes_per_side,
            width_cells     = width,
            has_sidewalk    = has_sidewalk,
            graph_level     = "district",
            world_uid       = world_uid,
        )

    # Горизонтальные рёбра
    for row in range(n_rows):
        for col in range(n_cols - 1):
            edges.append(make_edge(get_or_create(col, row), get_or_create(col + 1, row)))

    # Вертикальные рёбра
    for col in range(n_cols):
        for row in range(n_rows - 1):
            edges.append(make_edge(get_or_create(col, row), get_or_create(col, row + 1)))

    # --- through_road коридоры из entry_nodes ---
    _apply_through_roads(slot.entry_nodes, node_grid, edges, connection_type, lanes_per_side, width, has_sidewalk, world_uid, ox, oy, step_x, step_y, n_cols, n_rows, z)

    return list(node_grid.values()), edges


def _apply_through_roads(
    entry_nodes:     list[ConnectionEntry],
    node_grid:       dict[tuple[int, int], ConnectionNode],
    edges:           list[ConnectionEdge],
    connection_type: str,
    lanes_per_side:  int,
    width:           int | None,
    has_sidewalk:    bool,
    world_uid:       str,
    ox: int, oy: int,
    step_x: int, step_y: int,
    n_cols: int, n_rows: int,
    z: int,
) -> None:
    """
    Для каждой пары through_road (вход + выход на противоположных гранях)
    соединяет ближайшие узлы сетки прямым коридором.
    Узлы из SettlementAssembler (entry_nodes) добавляются в node_grid и
    подключаются к ближайшему узлу сетки на своей грани.
    """
    through_map: dict[str, ConnectionEntry] = {}
    for entry in entry_nodes:
        if entry.role == "through_road" and entry.paired_exit_uid is not None:
            through_map[entry.node.node_uid] = entry

    processed_pairs: set[frozenset[str]] = set()

    for entry in entry_nodes:
        if entry.role != "through_road":
            continue
        if entry.paired_exit_uid is None:
            continue

        pair_key = frozenset([entry.node.node_uid, entry.paired_exit_uid])
        if pair_key in processed_pairs:
            continue
        processed_pairs.add(pair_key)

        exit_entry = through_map.get(entry.paired_exit_uid)
        if exit_entry is None:
            continue

        # Вставляем pre-built узлы SettlementAssembler в граф
        node_in  = entry.node
        node_out = exit_entry.node

        # Snap: находим ближайшую колонку/строку сетки для узла входа
        in_snap  = _snap_to_grid(node_in,  ox, oy, step_x, step_y, n_cols, n_rows, entry.facing)
        out_snap = _snap_to_grid(node_out, ox, oy, step_x, step_y, n_cols, n_rows, exit_entry.facing)

        grid_in  = node_grid.get(in_snap)
        grid_out = node_grid.get(out_snap)
        if grid_in is None or grid_out is None:
            continue

        # Прокладываем через_road ребро поверх grid_in→grid_out
        # (сетка уже соединена горизонтально/вертикально — through_road использует те же рёбра,
        #  но с типом дороги из entry_node, который может отличаться от основного)
        edge = ConnectionEdge(
            edge_uid        = f"e_through_{node_in.node_uid}_{node_out.node_uid}",
            from_node_uid   = grid_in.node_uid,
            to_node_uid     = grid_out.node_uid,
            connection_type = entry.connection_type,
            bidirectional   = True,
            lanes_per_side  = lanes_per_side,
            width_cells     = resolve_width(entry.connection_type, lanes_per_side, True),
            has_sidewalk    = has_sidewalk,
            graph_level     = "district",
            world_uid       = world_uid,
        )
        edges.append(edge)


def _snap_to_grid(
    node:   ConnectionNode,
    ox: int, oy: int,
    step_x: int, step_y: int,
    n_cols: int, n_rows: int,
    facing: Facing,
) -> tuple[int, int]:
    """(col, row) ближайшего узла сетки к точке входа на грани/углу bbox."""
    return snap_bbox_edge_to_grid(
        facing,
        node.x - ox,
        node.y - oy,
        step_x,
        step_y,
        n_cols,
        n_rows,
    )
