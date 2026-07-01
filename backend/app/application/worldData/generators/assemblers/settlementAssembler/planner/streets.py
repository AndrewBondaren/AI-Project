import logging
import uuid
from random import Random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import ConnectionEntry
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_gate_line_coords,
    grid_dimension,
)
from app.application.worldData.generators.road.blockSize import block_size_for_density
from app.application.worldData.generators.road.connectionPolicy import resolve_has_sidewalk
from app.application.worldData.generators.road.sidewalkWidthResolver import resolve_sidewalk_width
from app.application.worldData.generators.road.roadTravelResolver import effective_travel_modifier
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.application.worldData.generators.utils.facing import Facing
from app.dataModel.materials import DEFAULT_ROAD_MATERIAL
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _city_has_sidewalk(skeleton: CitySkeleton) -> bool:
    """Perimeter/inter-district city roads: sidewalk unless settlement is sparse."""
    return skeleton.settlement_density != "sparse"


def _city_road_material(world: World, skeleton: CitySkeleton, rng: Random) -> str:
    return resolve_material(
        world, "road", skeleton.economic_tier, rng, DEFAULT_ROAD_MATERIAL,
    )


def _make_node(
    x: int, y: int, z: int,
    node_type: str,
    graph_level: str,
    world_uid: str,
    tag: str,
) -> ConnectionNode:
    """ConnectionNode x/y/z in WORLD_LOCAL_METERS."""
    return ConnectionNode(
        node_uid=f"{tag}_{x}_{y}_{z}_{uuid.uuid4().hex[:8]}",
        x=x, y=y, z=z,
        node_type=node_type,
        graph_level=graph_level,
        world_uid=world_uid,
    )


def _grid_lines(origin: int, side_m: int, block: int) -> list[int]:
    """Координаты origin, origin+block, … origin+side_m (границы включены)."""
    lines = [origin]
    pos = origin + block
    while pos < origin + side_m:
        lines.append(pos)
        pos += block
    end = origin + side_m
    if lines[-1] != end:
        lines.append(end)
    return lines


def _lines_in_range(lines: list[int], lo: int, hi: int) -> list[int]:
    return [v for v in lines if lo <= v <= hi]


def _connection_type(slot: DistrictSlot) -> str:
    connections = slot.district_template.get("connections") or []
    primary = connections[0] if connections else {}
    return primary.get("connection_type") or "road"


def plan_settlement_entries(
    slots:     list[DistrictSlot],
    skeleton:  CitySkeleton,
    origin_x:  int,
    origin_y:  int,
    side_m:    int,
    world_uid: str,
) -> None:
    """
    Заполняет slot.entry_nodes для всех районов.
    CoordinateSpace: WORLD_LOCAL_METERS on ConnectionNode x/y/z.
    Узлы на (x, y, z) дедуплицируются — соседние районы делят узел на общей границе.
    through_road: пары W↔E и S↔N на гранях с шагом block_size.
    entry_point: узлы на южной грани с шагом block_size.
    """
    block = block_size_for_density(skeleton.settlement_density)
    x_lines = _grid_lines(origin_x, side_m, block)
    y_lines = _grid_lines(origin_y, side_m, block)

    node_registry: dict[tuple[int, int, int], ConnectionNode] = {}

    def get_node(x: int, y: int, z: int, tag: str) -> ConnectionNode:
        key = (x, y, z)
        if key not in node_registry:
            node_registry[key] = _make_node(
                x, y, z, "intersection", "district", world_uid, tag,
            )
        return node_registry[key]

    for slot in slots:
        ox, oy = slot.origin_x, slot.origin_y
        w, d = slot.width_m, slot.depth_m
        z = slot.ground_z
        conn_type = _connection_type(slot)
        entries: list[ConnectionEntry] = []

        slot_y = _lines_in_range(y_lines, oy, oy + d)
        for y in slot_y:
            west = get_node(ox, y, z, "through_w")
            east = get_node(ox + w, y, z, "through_e")
            entries.append(ConnectionEntry(
                node=west, connection_type=conn_type, role="through_road",
                facing=Facing.WEST, paired_exit_uid=east.node_uid,
            ))
            entries.append(ConnectionEntry(
                node=east, connection_type=conn_type, role="through_road",
                facing=Facing.EAST, paired_exit_uid=west.node_uid,
            ))

        slot_x = _lines_in_range(x_lines, ox, ox + w)
        for x in slot_x:
            south = get_node(x, oy, z, "through_s")
            north = get_node(x, oy + d, z, "through_n")
            entries.append(ConnectionEntry(
                node=south, connection_type=conn_type, role="through_road",
                facing=Facing.SOUTH, paired_exit_uid=north.node_uid,
            ))
            entries.append(ConnectionEntry(
                node=north, connection_type=conn_type, role="through_road",
                facing=Facing.NORTH, paired_exit_uid=south.node_uid,
            ))

        x = ox + block
        while x < ox + w:
            node = get_node(x, oy, z, "entry_s")
            entries.append(ConnectionEntry(
                node=node, connection_type=conn_type, role="entry_point",
                facing=Facing.SOUTH, paired_exit_uid=None,
            ))
            x += block

        slot.entry_nodes = entries

        through = sum(1 for e in entries if e.role == "through_road") // 2
        entry_pts = sum(1 for e in entries if e.role == "entry_point")
        logger.info(
            "plan_settlement_entries slot | template=%s origin=(%d,%d) size=%dx%d"
            " connection_type=%s through_road_pairs=%d entry_points=%d",
            slot.district_template.get("system_name", "?"),
            ox,
            oy,
            w,
            d,
            conn_type,
            through,
            entry_pts,
        )

    logger.info(
        "plan_settlement_entries done | algorithm=block_size_grid block=%d density=%s"
        " x_lines=%d y_lines=%d slots=%d unique_nodes=%d",
        block,
        skeleton.settlement_density,
        len(x_lines),
        len(y_lines),
        len(slots),
        len(node_registry),
    )


def _collect_node_registry(
    slots: list[DistrictSlot],
) -> dict[tuple[int, int, int], ConnectionNode]:
    registry: dict[tuple[int, int, int], ConnectionNode] = {}
    for slot in slots:
        for entry in slot.entry_nodes:
            n = entry.node
            registry[(n.x, n.y, n.z)] = n
    return registry


def plan_city_street_grid(
    origin_x:       int,
    origin_y:       int,
    ground_z:       int,
    side_m:         int,
    cell_m:         int,
    district_slots: list[DistrictSlot],
    world_uid:      str,
    world:          World,
    rng:            Random,
    skeleton:       CitySkeleton,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    """
    settlement_gate на периметре footprint + кольцевая магистраль.
    CoordinateSpace: WORLD_LOCAL_METERS (origin_x/y, side_m, cell_m for gate spacing).
    Для n>1: city-level коридоры на внутренних границах между районами.
    """
    nodes: list[ConnectionNode] = []
    edges: list[ConnectionEdge] = []
    by_xy: dict[tuple[int, int], ConnectionNode] = {}
    district_nodes = _collect_node_registry(district_slots)

    def register(node: ConnectionNode) -> ConnectionNode:
        key = (node.x, node.y)
        if key not in by_xy:
            by_xy[key] = node
            if node not in nodes:
                nodes.append(node)
        return by_xy[key]

    def gate(x: int, y: int, label: str) -> ConnectionNode:
        key = (x, y)
        if key in by_xy:
            return by_xy[key]
        if (x, y, ground_z) in district_nodes:
            return register(district_nodes[(x, y, ground_z)])
        node = _make_node(x, y, ground_z, "settlement_gate", "city", world_uid, label)
        return register(node)

    xs = footprint_gate_line_coords(origin_x, side_m, cell_m)
    ys = footprint_gate_line_coords(origin_y, side_m, cell_m)

    south_gates = [gate(x, origin_y, "gate_s") for x in xs]
    north_gates = [gate(x, origin_y + side_m, "gate_n") for x in xs]
    west_gates  = [gate(origin_x, y, "gate_w") for y in ys]
    east_gates  = [gate(origin_x + side_m, y, "gate_e") for y in ys]

    width = resolve_width("road", lanes_per_side=1, bidirectional=True)
    road_material = _city_road_material(world, skeleton, rng)
    has_sidewalk  = _city_has_sidewalk(skeleton)
    sidewalk_width = resolve_sidewalk_width(skeleton.economic_tier, rng, world)
    logger.info(
        "plan_city_street_grid | tier=%r material=%r has_sidewalk=%s sidewalk_width=%d",
        skeleton.economic_tier,
        road_material,
        has_sidewalk,
        sidewalk_width,
    )

    def link_chain(chain: list[ConnectionNode], conn_type: str = "road") -> None:
        for a, b in zip(chain, chain[1:]):
            edges.append(ConnectionEdge(
                edge_uid=f"city_{a.node_uid}_{b.node_uid}",
                from_node_uid=a.node_uid,
                to_node_uid=b.node_uid,
                connection_type=conn_type,
                bidirectional=True,
                lanes_per_side=1,
                width_cells=width,
                material=road_material,
                has_sidewalk=has_sidewalk,
                graph_level="city",
                world_uid=world_uid,
            ))

    link_chain(south_gates)
    link_chain(north_gates)
    link_chain(west_gates)
    link_chain(east_gates)

    grid_n = grid_dimension(side_m, cell_m)
    block = block_size_for_density(skeleton.settlement_density)
    y_lines = _grid_lines(origin_y, side_m, block)
    x_lines = _grid_lines(origin_x, side_m, block)

    corridor_nodes: list[ConnectionNode] = []

    def city_corridor_node(x: int, y: int, tag: str) -> ConnectionNode:
        key = (x, y, ground_z)
        if key in district_nodes:
            return register(district_nodes[key])
        if (x, y) in by_xy:
            return by_xy[(x, y)]
        node = _make_node(x, y, ground_z, "intersection", "city", world_uid, tag)
        return register(node)

    if grid_n > 1:
        for i in range(1, grid_n):
            bx = origin_x + i * cell_m
            chain = [city_corridor_node(bx, y, "corridor_v") for y in y_lines]
            corridor_nodes.extend(chain)
            link_chain(chain)

        for j in range(1, grid_n):
            by = origin_y + j * cell_m
            chain = [city_corridor_node(x, by, "corridor_h") for x in x_lines]
            corridor_nodes.extend(chain)
            link_chain(chain)

    city_targets = list(by_xy.values())

    for slot in district_slots:
        for entry in slot.entry_nodes:
            if entry.role != "entry_point":
                continue
            entry_node = entry.node
            register(entry_node)
            nearest = min(
                city_targets,
                key=lambda g: abs(g.x - entry_node.x) + abs(g.y - entry_node.y),
            )
            edges.append(ConnectionEdge(
                edge_uid=f"city_link_{entry_node.node_uid}_{nearest.node_uid}",
                from_node_uid=entry_node.node_uid,
                to_node_uid=nearest.node_uid,
                connection_type=entry.connection_type,
                bidirectional=True,
                lanes_per_side=1,
                width_cells=width,
                material=road_material,
                has_sidewalk=resolve_has_sidewalk(
                    slot.district_template, entry.connection_type, world=world,
                ),
                graph_level="city",
                world_uid=world_uid,
            ))

    entry_links = [e for e in edges if e.edge_uid.startswith("city_link_")]
    if entry_links:
        sample = entry_links[0]
        logger.info(
            "plan_city_street_grid | sample_entry_link effective_travel_modifier=%.3f"
            " has_sidewalk=%s material=%r",
            effective_travel_modifier(world, sample),
            sample.has_sidewalk,
            sample.material,
        )

    corridor_algo = (
        "perimeter_ring+inter_district_corridors" if grid_n > 1 else "perimeter_ring"
    )
    logger.info(
        "plan_city_street_grid done | algorithm=%s side_m=%d cell_m=%d grid=%dx%d"
        " block=%d density=%s gates_per_side=(S%d N%d W%d E%d)"
        " nodes=%d edges=%d entry_links=%d",
        corridor_algo,
        side_m,
        cell_m,
        grid_n,
        grid_n,
        block,
        skeleton.settlement_density,
        len(south_gates),
        len(north_gates),
        len(west_gates),
        len(east_gates),
        len(nodes),
        len(edges),
        sum(1 for e in edges if e.edge_uid.startswith("city_link_")),
    )

    return nodes, edges
