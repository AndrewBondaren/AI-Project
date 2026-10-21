"""Physical level resolution over the elevation component hierarchy.

Small-to-large frontier bags retain dormant basins until a higher neighbour
reaches them. Only contacted fronts are joined; dry sills and river links do
not join levels. A final materialization pass contracts/expands to that level.
"""

from dataclasses import dataclass, field
from heapq import heappop, heappush

from app.application.worldData.generators.hydrology.water.depressionTree import DepressionTree
from app.application.worldData.generators.hydrology.water.waterSources import WaterSource
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSystemKind import WaterSystemKind
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.ids.waterSystemIdentity import water_system_uid


@dataclass
class _Group:
    members: set[int]
    level: int
    system_uid: str | None = None
    ocean: bool = False
    exterior: int | None = None


@dataclass
class _Bag:
    groups: set[int] = field(default_factory=set)
    heap: list[tuple[int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedWaterLevels:
    levels: tuple[int, ...]
    declared_levels: tuple[int, ...]
    parents: tuple[str | None, ...]
    unions: tuple[PhysicalWaterUnion, ...]


def resolve_water_levels(tree: DepressionTree, sources: tuple[WaterSource, ...], *,
                         world_uid: str, change_uid: str,
                         default_water_level: int) -> ResolvedWaterLevels:
    groups = [_Group({i}, source.spec.z_water_level,
                      ocean=source.spec.kind is BasinKind.OCEAN)
              for i, source in enumerate(sources)]
    parent = list(range(len(groups)))
    own_levels = [source.spec.z_water_level for source in sources]
    body_parents: list[str | None] = [None] * len(sources)
    unions: dict[str, PhysicalWaterUnion] = {}
    starts: dict[int, set[int]] = {}
    for i, source in enumerate(sources):
        for seed in source.seeds:
            index = tree.by_cell[seed]
            starts.setdefault(index, set()).add(i)

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != index:
            previous = parent[index]
            parent[index] = root
            index = previous
        return root

    def add(bag: _Bag, index: int) -> None:
        index = find(index)
        if index not in bag.groups:
            bag.groups.add(index)
            heappush(bag.heap, (-groups[index].level, index))

    def highest(bag: _Bag) -> int | None:
        while bag.heap:
            neg_level, index = bag.heap[0]
            root = find(index)
            if root != index or -neg_level != groups[root].level:
                heappop(bag.heap)
                bag.groups.discard(index)
                add(bag, root)
                continue
            return -neg_level
        return None

    bags: dict[int, _Bag] = {}
    for node_index, node in enumerate(tree.nodes):
        children = [bags.pop(child) for child in node.children]
        empty_branch = any(not bag.groups for bag in children)
        bag = max(children, key=lambda item: len(item.groups)) if children else _Bag()
        for other in children:
            if other is not bag:
                for index in other.groups:
                    add(bag, index)
        for index in sorted(starts.get(node_index, ())):
            add(bag, index)
        maximum = highest(bag)
        if maximum is not None and maximum > node.height:
            roots = {find(index) for index in bag.groups}
            # Preserve the body's own retained level before its first physical
            # parent. Interior shelf/ramp seeds of the same body are not rims.
            if empty_branch or len(roots) > 1 or node.boundary:
                for root in roots:
                    for i in groups[root].members:
                        if body_parents[i] is None:
                            limit = (default_water_level if node.boundary
                                     and sources[i].spec.kind is BasinKind.OCEAN else node.height)
                            own_levels[i] = min(own_levels[i], limit)
            first = min(roots)
            group = groups[first]
            if len(roots) > 1:
                members = set().union(*(groups[index].members for index in roots))
                child_uids = tuple(sorted(groups[index].system_uid for index in roots
                                          if groups[index].system_uid is not None))
                uid = water_system_uid(world_uid, change_uid,
                                       (sources[i].spec.source_uid for i in members),
                                       WaterSystemKind.PHYSICAL_MERGE)
                for i in members:
                    if body_parents[i] is None:
                        body_parents[i] = uid
                for child_uid in child_uids:
                    unions[child_uid] = unions[child_uid].model_copy(update={"parent_system_uid": uid})
                exterior = [groups[i].exterior for i in roots if groups[i].exterior is not None]
                group = _Group(members, maximum, uid, any(groups[i].ocean for i in roots),
                               min(exterior) if exterior else None)
                groups[first] = group
                for index in roots:
                    parent[index] = first
                unions[uid] = PhysicalWaterUnion(
                    water_system_uid=uid,
                    member_uids=tuple(sorted(sources[i].spec.source_uid for i in members)),
                    child_system_uids=child_uids, z_water_level=maximum,
                )
            if empty_branch:
                group.level = min(group.level, node.height)
            if node.boundary:
                group.exterior = node.height if group.exterior is None else min(group.exterior, node.height)
            if group.exterior is not None:
                group.level = default_water_level if group.ocean else min(group.level, group.exterior)
            bag = _Bag({first}, [(-group.level, first)])
        bags[node_index] = bag

    levels = tuple(groups[find(i)].level for i in range(len(sources)))
    # Resolve the whole physical ancestor chain once, rather than per-cell.
    effective: dict[str, int] = {}
    for i, level in enumerate(levels):
        uid = groups[find(i)].system_uid
        if uid is not None:
            effective[uid] = level
    for uid in reversed(tuple(unions)):
        union = unions[uid]
        level = effective[union.parent_system_uid] if union.parent_system_uid else effective[uid]
        effective[uid] = level
        unions[uid] = union.model_copy(update={"z_water_level": level})
    return ResolvedWaterLevels(levels, tuple(own_levels), tuple(body_parents), tuple(unions.values()))
