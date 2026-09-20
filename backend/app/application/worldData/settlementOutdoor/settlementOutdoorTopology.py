"""C23 topology skip + reload frozen district slots from SQL."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.application.jsonValidation.worldRow import district_templates, enabled_building_purposes
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import (
    ConnectionEntry,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
    resolve_settlement_specialization,
    slot_allowed_for_template,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    is_district_location,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.settlement.district.districtTopologySlot import DistrictTopologySlot
from app.dataModel.settlement.district.requiredStructureResolve import (
    unhosted_settlement_types,
    union_required_structures,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def has_authored_non_district_children(children: list[NamedLocation]) -> bool:
    return any(not is_district_location(child.system_location_type) for child in children)


def topology_districts(children: list[NamedLocation]) -> list[NamedLocation]:
    return [child for child in children if is_district_location(child.system_location_type)]


def city_nodes_for_settlement(
    nodes: list[ConnectionNode],
    settlement_uid: str,
) -> list[ConnectionNode]:
    return [node for node in nodes if node.location_uid == settlement_uid]


def has_city_settlement_gates(nodes: list[ConnectionNode]) -> bool:
    gate = ConnectionNodeType.SETTLEMENT_GATE.value
    city = GraphLevel.CITY.value
    return any(node.node_type == gate and node.graph_level == city for node in nodes)


def _frozen_topology_slot(row: NamedLocation) -> DistrictTopologySlot | None:
    if not row.district_topology:
        return None
    try:
        return DistrictTopologySlot.model_validate(row.district_topology)
    except ValidationError:
        return None


def has_frozen_c23_districts(children: list[NamedLocation]) -> bool:
    districts = topology_districts(children)
    if not districts:
        return False
    return all(_frozen_topology_slot(row) is not None for row in districts)


class DistrictAnchorError(ValueError):
    """Invalid packing anchor (both / miss / outside). HTTP 422."""


def topology_census(children: list[NamedLocation]) -> list[NamedLocation]:
    """C23 districts with frozen ``district_topology``, ordered by slot_index."""
    rows: list[tuple[int, NamedLocation]] = []
    for child in topology_districts(children):
        slot = _frozen_topology_slot(child)
        if slot is None:
            continue
        rows.append((slot.slot_index, child))
    rows.sort(key=lambda item: (item[0], item[1].location_uid))
    return [child for _, child in rows]


def _point_in_district_rect(slot: DistrictTopologySlot, x: int, y: int) -> bool:
    return (
        slot.origin_x <= x < slot.origin_x + slot.width_fine
        and slot.origin_y <= y < slot.origin_y + slot.depth_fine
    )


def resolve_district_uid(
    census: list[NamedLocation],
    *,
    district_uid: str | None = None,
    at_x: int | None = None,
    at_y: int | None = None,
) -> str:
    """Map canonical ``district_uid`` or world-fine ``at`` onto a C23 census uid."""
    has_uid = bool(district_uid)
    has_at_part = at_x is not None or at_y is not None
    if has_uid and has_at_part:
        raise DistrictAnchorError("district_uid and at cannot both be set")
    if has_at_part and (at_x is None or at_y is None):
        raise DistrictAnchorError("at_x and at_y are required together")
    if has_uid:
        for row in census:
            if row.location_uid == district_uid:
                return row.location_uid
        raise DistrictAnchorError(
            f"district '{district_uid}' is not a C23 census slot"
        )
    if at_x is not None and at_y is not None:
        for row in census:
            slot = _frozen_topology_slot(row)
            if slot is None:
                continue
            if _point_in_district_rect(slot, at_x, at_y):
                return row.location_uid
        raise DistrictAnchorError("at point is outside all C23 district slots")
    raise DistrictAnchorError("district_uid or at_x+at_y required")


def slot_for_census_row(
    slots: list[DistrictSlot],
    row: NamedLocation,
) -> DistrictSlot | None:
    wire = _frozen_topology_slot(row)
    if wire is None:
        return None
    for slot in slots:
        if slot.slot_index == wire.slot_index:
            return slot
    return None


def should_skip_topology(
    children: list[NamedLocation],
    settlement_nodes: list[ConnectionNode],
) -> bool:
    if has_authored_non_district_children(children):
        return True
    if not has_frozen_c23_districts(children):
        return False
    return has_city_settlement_gates(settlement_nodes)


def load_topology_slots(
    world: World,
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    districts: list[NamedLocation],
) -> list[DistrictSlot] | None:
    rows = [child for child in districts if child.district_topology]
    if len(rows) != len(districts) or not rows:
        return None
    parsed: list[tuple[DistrictTopologySlot, NamedLocation]] = []
    for row in rows:
        parsed.append((DistrictTopologySlot.model_validate(row.district_topology), row))
    parsed.sort(key=lambda item: item[0].slot_index)
    templates = district_templates(world)
    enabled = enabled_building_purposes(world)
    resolved = resolve_settlement_specialization(world, settlement, skeleton)
    slots: list[DistrictSlot] = []
    nodes_by_uid: dict[str, ConnectionNode] = {}
    for wire, row in parsed:
        template = templates.entry_for(wire.template_system_name)
        if template is None:
            return None
        allowed = slot_allowed_for_template(template, resolved)
        required = union_required_structures(
            list(resolved.required_types),
            list(template.required_structures or []),
            allowed,
            enabled,
        )
        entries: list[ConnectionEntry] = []
        for item in wire.entries:
            node = nodes_by_uid.get(item.node_uid)
            if node is None:
                node = ConnectionNode(
                    node_uid=item.node_uid,
                    x=item.x,
                    y=item.y,
                    z=item.z,
                    node_type=ConnectionNodeType.INTERSECTION.value,
                    graph_level=GraphLevel.DISTRICT.value,
                    world_uid=settlement.world_uid,
                    location_uid=settlement.location_uid,
                )
                nodes_by_uid[item.node_uid] = node
            entries.append(ConnectionEntry(
                node=node,
                connection_type=item.connection_type,
                role=item.role,
                facing=item.facing,
                paired_exit_uid=item.paired_exit_uid,
            ))
        slots.append(DistrictSlot(
            origin_x=wire.origin_x,
            origin_y=wire.origin_y,
            width_fine=wire.width_fine,
            depth_fine=wire.depth_fine,
            ground_z=wire.ground_z,
            district_template=template,
            entry_nodes=entries,
            required_structures=required,
            allowed_structure_types=allowed,
            cell_x=wire.cell_x,
            cell_y=wire.cell_y,
            subject_tags=dict(resolved.subject_tags),
            slot_index=wire.slot_index,
        ))
    leftover = unhosted_settlement_types(
        list(resolved.required_types),
        [slot.allowed_structure_types for slot in slots],
        enabled,
    )
    for type_name in leftover:
        logger.warning(
            "Settlement required purpose has no host district | settlement=%s"
            " structure_type=%s — leftover",
            settlement.location_uid,
            type_name,
        )
    return slots


def city_graph_for_settlement(
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    settlement_uid: str,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    city_nodes = city_nodes_for_settlement(nodes, settlement_uid)
    uids = {node.node_uid for node in city_nodes}
    city_edges = [
        edge for edge in edges
        if edge.from_node_uid in uids or edge.to_node_uid in uids
    ]
    missing = set()
    for edge in city_edges:
        if edge.from_node_uid not in uids:
            missing.add(edge.from_node_uid)
        if edge.to_node_uid not in uids:
            missing.add(edge.to_node_uid)
    extra = [node for node in nodes if node.node_uid in missing]
    return city_nodes + extra, city_edges
