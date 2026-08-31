"""Area-level connection graph only. No grade cells / partition_height."""

from __future__ import annotations

import uuid

from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThreshold,
    AreaThresholdKind,
)
from app.application.worldData.generators.assemblers.areaAssembler.streetApproach import (
    ApproachForm,
    StreetApproach,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.spatial.facing import GRID_OUTWARD_DELTA, Facing
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation


def _yard_path_type() -> str:
    entry = WorldConnectionTypeRegistry.canonical_engine().entry_for("yard_path")
    if entry is not None:
        return entry.system_connection_type
    trail = WorldConnectionTypeRegistry.canonical_engine().entry_for("trail")
    return trail.system_connection_type if trail is not None else "trail"


def _threshold_node_type(kind: AreaThresholdKind) -> ConnectionNodeType:
    if kind == AreaThresholdKind.DOOR:
        return ConnectionNodeType.BUILDING_ENTRANCE
    return ConnectionNodeType.WAYPOINT


def _make_node(
    x: int,
    y: int,
    z: int,
    node_type: ConnectionNodeType,
    world_uid: str,
    tag: str,
    location_uid: str | None = None,
) -> ConnectionNode:
    return ConnectionNode(
        node_uid=f"a_{tag}_{x}_{y}_{z}_{uuid.uuid4().hex[:8]}",
        x=x,
        y=y,
        z=z,
        node_type=node_type.value,
        graph_level=GraphLevel.AREA.value,
        world_uid=world_uid,
        location_uid=location_uid,
    )


def _link(
    a: ConnectionNode,
    b: ConnectionNode,
    world_uid: str,
    conn_type: str,
) -> ConnectionEdge:
    return ConnectionEdge(
        edge_uid=f"a_{a.node_uid}_{b.node_uid}",
        from_node_uid=a.node_uid,
        to_node_uid=b.node_uid,
        connection_type=conn_type,
        graph_level=GraphLevel.AREA.value,
        world_uid=world_uid,
        bidirectional=True,
    )


def build_area_paths(
    *,
    world_uid: str,
    threshold: AreaThreshold,
    approach: StreetApproach | None,
    facing: Facing,
    building: NamedLocation | None,
    door_xy: tuple[int, int] | None,
    yard_approach: StreetApproach | None = None,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    if not threshold.cells:
        return [], []
    tx, ty = threshold.cells[0]
    loc = building.location_uid if building is not None else None
    path_type = _yard_path_type()
    thresh_node = _make_node(
        tx, ty, threshold.z, _threshold_node_type(threshold.kind),
        world_uid, "thr", loc,
    )
    nodes: list[ConnectionNode] = [thresh_node]
    edges: list[ConnectionEdge] = []

    street_xy: tuple[int, int] | None = None
    street_z = threshold.z
    if approach is not None and approach.ray:
        street_xy = approach.ray[-1]
        street_z = approach.z_far
    else:
        delta = GRID_OUTWARD_DELTA.get(facing)
        if delta is not None:
            street_xy = (tx + delta[0], ty + delta[1])
        if approach is not None:
            street_z = approach.z_far

    if street_xy is not None:
        street_node = _make_node(
            street_xy[0], street_xy[1], street_z,
            ConnectionNodeType.WAYPOINT, world_uid, "st",
        )
        nodes.append(street_node)
        if approach is not None and approach.form != ApproachForm.NONE and len(approach.ray) > 1:
            prev = street_node
            z_cur = street_z
            # ray is origin→street; graph walks street→threshold
            for cell in reversed(approach.ray[:-1]):
                wp = _make_node(
                    cell[0], cell[1], z_cur,
                    ConnectionNodeType.WAYPOINT, world_uid, "ray",
                )
                nodes.append(wp)
                edges.append(_link(prev, wp, world_uid, path_type))
                prev = wp
            edges.append(_link(prev, thresh_node, world_uid, path_type))
        else:
            edges.append(_link(street_node, thresh_node, world_uid, path_type))

    if (
        building is not None
        and threshold.kind != AreaThresholdKind.DOOR
        and door_xy is not None
    ):
        door_z = int(building.map_z or threshold.z)
        door_node = _make_node(
            door_xy[0], door_xy[1], door_z,
            ConnectionNodeType.BUILDING_ENTRANCE, world_uid, "door",
            building.location_uid,
        )
        nodes.append(door_node)
        if yard_approach is not None and yard_approach.form != ApproachForm.NONE and yard_approach.ray:
            prev = thresh_node
            for cell in yard_approach.ray:
                if cell == door_xy:
                    continue
                wp = _make_node(
                    cell[0], cell[1], yard_approach.z_near,
                    ConnectionNodeType.WAYPOINT, world_uid, "yard",
                    building.location_uid,
                )
                nodes.append(wp)
                edges.append(_link(prev, wp, world_uid, path_type))
                prev = wp
            edges.append(_link(prev, door_node, world_uid, path_type))
        else:
            edges.append(_link(thresh_node, door_node, world_uid, path_type))

    return nodes, edges
