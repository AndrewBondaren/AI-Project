"""Elevation-ordered component hierarchy (priority-flood / union-find).

Equal-height plateaus are activated atomically, so a flat sill cannot become a
false outlet merely because one cell was popped first. Each terrain cell and
edge is visited once; the elevation heap costs O(N log N). No z is written.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from heapq import heapify, heappop

from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.dataModel.topology.worldTopology import Coord, WorldTopology


@dataclass
class DepressionNode:
    height: int
    cells: tuple[Coord, ...]
    children: tuple[int, ...]
    boundary: bool
    parent: int | None = None
    spill: int | None = None


@dataclass
class DepressionTree:
    nodes: list[DepressionNode] = field(default_factory=list)
    by_cell: dict[Coord, int] = field(default_factory=dict)
    roots: tuple[int, ...] = ()


def depression_tree(surface_z: Mapping[Coord, int], topology: WorldTopology) -> DepressionTree:
    tree = DepressionTree()
    parent: dict[Coord, Coord] = {}
    sizes: dict[Coord, int] = {}
    top: dict[Coord, int] = {}
    neighbors = {}
    for cell in surface_z:
        if topology.canonicalize(*cell) != cell:
            raise ValueError(f"noncanonical water elevation at {cell}")
        adjacent = canonical_neighbors4(topology, cell)
        if any(other not in surface_z for other in adjacent):
            raise ValueError(f"unresolved water: incomplete terrain at {cell}")
        neighbors[cell] = adjacent

    def find(cell: Coord) -> Coord:
        root = cell
        while parent[root] != root:
            root = parent[root]
        while parent[cell] != cell:
            previous = parent[cell]
            parent[cell] = root
            cell = previous
        return root

    def join(a: Coord, b: Coord) -> None:
        a, b = find(a), find(b)
        if a == b:
            return
        if sizes[a] < sizes[b]:
            a, b = b, a
        parent[b] = a
        sizes[a] += sizes[b]

    heap = [(z, cell[1], cell[0]) for cell, z in surface_z.items()]
    heapify(heap)
    while heap:
        height = heap[0][0]
        cells = []
        while heap and heap[0][0] == height:
            _, y, x = heappop(heap)
            cells.append((x, y))
        old_children = {}
        for cell in cells:
            old_children[cell] = {top[find(n)] for n in neighbors[cell]
                                  if n in parent and surface_z[n] < height}
        for cell in cells:
            parent[cell], sizes[cell] = cell, 1
        for cell in cells:
            for neighbor in neighbors[cell]:
                if neighbor in parent:
                    join(cell, neighbor)
        batches: dict[Coord, list[Coord]] = defaultdict(list)
        for cell in cells:
            batches[find(cell)].append(cell)
        for root, plateau in batches.items():
            children = set().union(*(old_children[cell] for cell in plateau))
            node_id = len(tree.nodes)
            tree.nodes.append(DepressionNode(height, tuple(plateau), tuple(sorted(children)),
                                              any(len(neighbors[c]) < 4 for c in plateau)))
            for child in children:
                tree.nodes[child].parent = node_id
            for cell in plateau:
                tree.by_cell[cell] = node_id
            top[root] = node_id
    tree.roots = tuple(i for i, node in enumerate(tree.nodes) if node.parent is None)
    stack = [(root, None) for root in tree.roots]
    while stack:
        index, inherited = stack.pop()
        node = tree.nodes[index]
        node.spill = node.height if node.boundary else inherited
        child_spill = node.height if node.boundary or len(node.children) > 1 else inherited
        stack.extend((child, child_spill) for child in node.children)
    return tree
