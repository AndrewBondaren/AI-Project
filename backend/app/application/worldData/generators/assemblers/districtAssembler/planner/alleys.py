"""Alleys between plots of one module / center cluster — C22 §5.5."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import NamedTuple

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
from app.application.worldData.generators.road.connectionPolicy import sidewalk_of
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    district_connection_node_uid,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.locations.settlement.district.districtConnection import (
    DistrictConnection,
    street_classes_for,
)
from app.dataModel.locations.settlement.enums.districtStreetRole import DistrictStreetRole
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode

Coord = tuple[int, int]


def alley_connection_type() -> str:
    return WorldConnectionTypeRegistry.require_engine("alley")


def alley_from_template(slot: DistrictSlot) -> DistrictConnection | None:
    return street_classes_for(slot.district_template).alley


def _cells_bbox(cells: list[Coord]) -> tuple[int, int, int, int]:
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return min(xs), min(ys), max(xs), max(ys)


class AlleySegment(NamedTuple):
    gap: int
    start: Coord
    end: Coord


def _alley_segment(
    plot_a: AreaPlacement,
    plot_b: AreaPlacement,
) -> AlleySegment:
    """Free gap between two plots and the alley centre line across it.

    Symmetric in ``plot_a`` / ``plot_b``. The line runs through the middle of the
    gap, perpendicular to the axis that separates the plots, spanning both
    reservations so it reaches the frame.
    """
    ax0, ay0, ax1, ay1 = _cells_bbox(
        plot_a.area_slot.cells or [(plot_a.building_x, plot_a.building_y)],
    )
    bx0, by0, bx1, by1 = _cells_bbox(
        plot_b.area_slot.cells or [(plot_b.building_x, plot_b.building_y)],
    )
    gap_x = max(bx0 - ax1, ax0 - bx1) - 1
    gap_y = max(by0 - ay1, ay0 - by1) - 1
    ra = plot_a.reservation.rect_xy if plot_a.reservation is not None else (ax0, ay0, ax1, ay1)
    rb = plot_b.reservation.rect_xy if plot_b.reservation is not None else (bx0, by0, bx1, by1)
    if gap_x >= gap_y:
        x = min(ax1, bx1) + 1 + gap_x // 2
        return AlleySegment(gap_x, (x, min(ra[1], rb[1])), (x, max(ra[3], rb[3])))
    y = min(ay1, by1) + 1 + gap_y // 2
    return AlleySegment(gap_y, (min(ra[0], rb[0]), y), (max(ra[2], rb[2]), y))


def _emit_alley_for_group(
    *,
    district: str,
    alley: DistrictConnection | None,
    alley_type: str,
    width: int,
    has_sidewalk: bool,
    group: list[AreaPlacement],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    world_uid: str,
    z_of: Callable[[int, int], int],
    edge_roles: dict[str, DistrictStreetRole] | None,
    edge_key: str,
) -> None:
    if alley is None:
        packing_info(
            PackingStep.ALLEY, district=district,
            n_plots=len(group), alley="no", reason=PackingReason.NOT_IN_SETTINGS,
        )
        return
    if len(group) < 2:
        packing_info(
            PackingStep.ALLEY, district=district,
            n_plots=len(group), alley="no", reason=PackingReason.SINGLE_PLOT,
        )
        return
    segment = _alley_segment(group[0], group[1])
    if segment.gap < width:
        packing_info(
            PackingStep.ALLEY, district=district,
            n_plots=len(group), alley="no", reason=PackingReason.WIDTH,
            width_cells=width,
        )
        return
    (sx, sy), (ex, ey) = segment.start, segment.end
    from_node = _node_at(nodes, sx, sy, z_of(sx, sy), world_uid)
    to_node = _node_at(nodes, ex, ey, z_of(ex, ey), world_uid)
    if from_node not in nodes:
        nodes.append(from_node)
    if to_node not in nodes:
        nodes.append(to_node)
    edge = ConnectionEdge(
        edge_uid=f"e_alley_{edge_key}_{from_node.node_uid}",
        from_node_uid=from_node.node_uid,
        to_node_uid=to_node.node_uid,
        connection_type=alley_type,
        width_cells=width,
        has_sidewalk=has_sidewalk,
        graph_level=GraphLevel.DISTRICT.value,
        world_uid=world_uid,
    )
    edges.append(edge)
    if edge_roles is not None:
        edge_roles[edge.edge_uid] = DistrictStreetRole.BACK_ALLEY
    packing_info(
        PackingStep.ALLEY, district=district,
        n_plots=len(group), alley="yes", reason=PackingReason.FROM_CONNECTIONS,
        width_cells=width,
    )


def add_alleys(
    slot: DistrictSlot,
    placements: list[AreaPlacement],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    world_uid: str,
    edge_roles: dict[str, DistrictStreetRole] | None = None,
    surface: dict[Coord, int] | None = None,
) -> None:
    """Alley thread from back_alley role or connection_type=alley when ≥2 plots fit."""
    district = slot.district_template.system_name
    z_lookup = surface or {}

    def z_of(x: int, y: int) -> int:
        return int(z_lookup.get((x, y), slot.ground_z))

    alley = alley_from_template(slot)
    by_module: dict[tuple[int, int], list[AreaPlacement]] = defaultdict(list)
    by_cluster: dict[str, list[AreaPlacement]] = defaultdict(list)
    for placement in placements:
        res = placement.reservation
        if res is None:
            continue
        if res.cluster_id is not None:
            by_cluster[res.cluster_id].append(placement)
            continue
        by_module[(res.col, res.row)].append(placement)

    alley_type = alley.connection_type if alley is not None else alley_connection_type()
    width = resolve_width(alley_type)
    if width is None:
        packing_info(
            PackingStep.ALLEY, district=district,
            alley="no", reason=PackingReason.WIDTH,
        )
        return
    has_sidewalk = sidewalk_of(alley) if alley is not None else False
    for (col, row), group in by_module.items():
        _emit_alley_for_group(
            district=district,
            alley=alley,
            alley_type=alley_type,
            width=width,
            has_sidewalk=has_sidewalk,
            group=group,
            nodes=nodes,
            edges=edges,
            world_uid=world_uid,
            z_of=z_of,
            edge_roles=edge_roles,
            edge_key=f"{col}_{row}",
        )
    for cluster_id, group in by_cluster.items():
        _emit_alley_for_group(
            district=district,
            alley=alley,
            alley_type=alley_type,
            width=width,
            has_sidewalk=has_sidewalk,
            group=group,
            nodes=nodes,
            edges=edges,
            world_uid=world_uid,
            z_of=z_of,
            edge_roles=edge_roles,
            edge_key=f"cluster_{cluster_id.replace(':', '_')}",
        )


def _node_at(
    existing: list[ConnectionNode],
    x: int,
    y: int,
    z: int,
    world_uid: str,
) -> ConnectionNode:
    district_level = GraphLevel.DISTRICT.value
    for node in existing:
        if (
            node.x == x and node.y == y and node.z == z
            and node.graph_level == district_level
        ):
            return node
    return ConnectionNode(
        node_uid=district_connection_node_uid(world_uid, "alley", x, y, z),
        x=x,
        y=y,
        z=z,
        node_type=ConnectionNodeType.INTERSECTION.value,
        graph_level=district_level,
        world_uid=world_uid,
    )
