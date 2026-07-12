"""Declare lake shoreline → LakeSpec — D HY-3."""

from __future__ import annotations

from app.application.worldData.generators.terrain.hydrology.basinKindResolver import (
    resolve_lake_basin_role,
)
from app.application.worldData.generators.terrain.hydrology.declaredEdges import (
    extract_declared_segments,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    LakeSpec,
    LoadedConnectionGraph,
)
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.db.models.namedLocation import NamedLocation


def _union_find_parent(parent: dict[tuple[int, int], tuple[int, int]], p: tuple[int, int]) -> tuple[int, int]:
    root = p
    while parent[root] != root:
        parent[root] = parent[parent[root]]
        root = parent[root]
    return root


def _group_segments(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
) -> list[list[tuple[tuple[int, int], tuple[int, int]]]]:
    if not segments:
        return []
    parent: dict[tuple[int, int], tuple[int, int]] = {}

    def ensure(p: tuple[int, int]) -> None:
        if p not in parent:
            parent[p] = p

    def union(a: tuple[int, int], b: tuple[int, int]) -> None:
        ensure(a)
        ensure(b)
        ra, rb = _union_find_parent(parent, a), _union_find_parent(parent, b)
        parent[ra] = rb

    for a, b in segments:
        union(a, b)

    buckets: dict[tuple[int, int], list[tuple[tuple[int, int], tuple[int, int]]]] = {}
    for seg in segments:
        root = _union_find_parent(parent, seg[0])
        buckets.setdefault(root, []).append(seg)
    return list(buckets.values())


def _location_uid_for_group(
    group: list[tuple[tuple[int, int], tuple[int, int]]],
    graph: LoadedConnectionGraph,
) -> str | None:
    points = {p for seg in group for p in seg}
    for node in graph.nodes:
        if (node.gx, node.gy) in points and node.location_uid:
            return node.location_uid
    return None


def extract_lake_specs(
    graph: LoadedConnectionGraph,
    locations: list[NamedLocation],
    *,
    world_uid: str,
) -> list[LakeSpec]:
    segments = extract_declared_segments(graph, HydrologyConnectionType.LAKE_SHORELINE)
    if not segments:
        return []
    loc_map = {loc.location_uid: loc for loc in locations}
    specs: list[LakeSpec] = []
    for group in _group_segments(segments):
        location_uid = _location_uid_for_group(group, graph)
        open_role = resolve_lake_basin_role(
            location_uid,
            loc_map,
            world_uid=world_uid,
            connection_type=HydrologyConnectionType.LAKE_SHORELINE.value,
        )
        specs.append(LakeSpec(
            shoreline_segments=group,
            location_uid=location_uid,
            open_water_role=open_role,
        ))
    return specs
