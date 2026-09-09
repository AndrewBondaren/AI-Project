"""SettlementLayout → SQL rows + pack wire. Pure; no I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayoutExtract import (
    collect_connection_graph,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorShell import (
    cells_to_shell_wires,
    outdoor_shell_wires,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    building_type_entry,
    district_type_entry,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    area_uid,
    building_location_uid,
    district_location_uid,
    entry_uid,
    level_uid,
)
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.locations.enums.entryRole import EntryRole
from app.dataModel.settlement.district.districtTopologySlot import (
    DistrictTopologyEntry,
    DistrictTopologySlot,
)
from app.dataModel.structure.enums.passageType import PassageType
from app.dataModel.worldPack.settlementStructureWire import (
    AreaSlotWire,
    AreaStructureWire,
    BuildingShellWire,
    DistrictStructureWire,
    SettlementStructureWire,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationEntryPoint import LocationEntryPoint
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.namedLocation import NamedLocation


class SettlementOutdoorExtractError(ValueError):
    """Persist-time extract invariant (e.g. missing front door)."""


@dataclass
class ExtractedSettlement:
    districts: list[NamedLocation]
    buildings: list[NamedLocation]
    levels: list[LocationLevel]
    entry_points: list[LocationEntryPoint]
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]
    wire: SettlementStructureWire


@dataclass
class ExtractedTopology:
    districts: list[NamedLocation]
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]


def topology_slot_wire(slot: DistrictSlot, *, slot_index: int) -> DistrictTopologySlot:
    entries = tuple(
        DistrictTopologyEntry(
            node_uid=entry.node.node_uid,
            x=entry.node.x,
            y=entry.node.y,
            z=entry.node.z,
            role=entry.role,
            facing=entry.facing,
            connection_type=entry.connection_type,
            paired_exit_uid=entry.paired_exit_uid,
        )
        for entry in slot.entry_nodes
    )
    return DistrictTopologySlot(
        cell_x=slot.cell_x,
        cell_y=slot.cell_y,
        origin_x=slot.origin_x,
        origin_y=slot.origin_y,
        width_fine=slot.width_fine,
        depth_fine=slot.depth_fine,
        ground_z=slot.ground_z,
        template_system_name=slot.district_template.system_name,
        slot_index=slot_index,
        entries=entries,
    )


def _city_topology_graph(
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    city = GraphLevel.CITY.value
    city_edges = [edge for edge in edges if edge.graph_level == city]
    keep = {node.node_uid for node in nodes if node.graph_level == city}
    for edge in city_edges:
        keep.add(edge.from_node_uid)
        keep.add(edge.to_node_uid)
    city_nodes = [node for node in nodes if node.node_uid in keep]
    return city_nodes, city_edges


def extract_topology(
    settlement: NamedLocation,
    slots: list[DistrictSlot],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> ExtractedTopology:
    district_type = district_type_entry()
    districts: list[NamedLocation] = []
    for d_index, slot in enumerate(slots):
        template = slot.district_template
        d_uid = district_location_uid(
            settlement.location_uid, template.system_name, d_index,
        )
        districts.append(NamedLocation(
            location_uid=d_uid,
            world_uid=settlement.world_uid,
            display_name=template.display_name,
            system_location_type=district_type.system_type,
            system_location_subtype=template.district_subtype,
            created_at=settlement.created_at,
            parent_location_uid=settlement.location_uid,
            is_outdoor=bool(district_type.is_outdoor),
            is_accessible=True,
            is_selectable=True,
            map_x=slot.origin_x,
            map_y=slot.origin_y,
            map_z=slot.ground_z,
            state_uid=settlement.state_uid,
            system_template_uid=template.system_name,
            district_topology=topology_slot_wire(slot, slot_index=d_index).model_dump(mode="json"),
        ))
    city_nodes, city_edges = _city_topology_graph(nodes, edges)
    return ExtractedTopology(districts=districts, nodes=city_nodes, edges=city_edges)


def _role_for_passage(passage: LocationPassage) -> EntryRole | None:
    if passage.from_level_uid is not None:
        return None
    pt = PassageType.from_wire(passage.system_passage_type)
    if pt == PassageType.MAIN_ENTRANCE:
        return EntryRole.FRONT
    if pt == PassageType.SERVICE_ENTRANCE:
        return EntryRole.SERVICE
    return None


def _entry_level(
    new_levels: list[LocationLevel],
    old_to_new: dict[str, str],
    passage: LocationPassage,
    building: NamedLocation,
) -> LocationLevel | None:
    mapped = old_to_new.get(passage.to_level_uid)
    if mapped:
        found = next((lv for lv in new_levels if lv.level_uid == mapped), None)
        if found is not None:
            return found
    ground = building.map_z
    if ground is not None:
        return next((lv for lv in new_levels if lv.z == ground), None)
    return None


def extract_settlement(settlement: NamedLocation, layout: SettlementLayout) -> ExtractedSettlement:
    district_type = district_type_entry()
    building_type = building_type_entry()
    district_is_outdoor = bool(district_type.is_outdoor)
    building_is_outdoor = bool(building_type.is_outdoor)
    district_system_type = district_type.system_type
    building_system_type = building_type.system_type

    districts: list[NamedLocation] = []
    buildings: list[NamedLocation] = []
    levels_out: list[LocationLevel] = []
    entries: list[LocationEntryPoint] = []
    district_wires: list[DistrictStructureWire] = []

    for d_index, district_layout in enumerate(layout.district_layouts):
        slot = district_layout.slot
        template = slot.district_template
        d_uid = district_location_uid(
            settlement.location_uid, template.system_name, d_index,
        )
        district_nl = NamedLocation(
            location_uid=d_uid,
            world_uid=settlement.world_uid,
            display_name=template.display_name,
            system_location_type=district_system_type,
            system_location_subtype=template.district_subtype,
            created_at=settlement.created_at,
            parent_location_uid=settlement.location_uid,
            is_outdoor=district_is_outdoor,
            is_accessible=True,
            is_selectable=True,
            map_x=slot.origin_x,
            map_y=slot.origin_y,
            map_z=slot.ground_z,
            state_uid=settlement.state_uid,
            system_template_uid=template.system_name,
            district_topology=topology_slot_wire(slot, slot_index=d_index).model_dump(mode="json"),
        )
        districts.append(district_nl)
        area_wires: list[AreaStructureWire] = []

        for area in district_layout.area_layouts:
            area_slot = area.slot
            slot_cells = list(area_slot.cells)
            if not slot_cells:
                slot_cells = [(0, 0)]
            min_x = min(x for x, _ in slot_cells)
            min_y = min(y for _, y in slot_cells)
            a_uid = area_uid(d_uid, min_x, min_y, area_slot.facing)
            probe = area.building_location

            if probe is None:
                area_wires.append(AreaStructureWire(
                    area_uid=a_uid,
                    slot=AreaSlotWire(
                        cells=list(dict.fromkeys(slot_cells)),
                        ground_z=area_slot.ground_z,
                        facing=area_slot.facing,
                        height=area_slot.height,
                        z_deep=area_slot.z_deep,
                    ),
                    barrier_cells=cells_to_shell_wires(area.barrier_cells),
                    yard_cells=cells_to_shell_wires(area.yard_cells),
                    small_layouts=[],
                    buildings=[],
                ))
                continue

            bx = int(probe.map_x or 0)
            by = int(probe.map_y or 0)
            template_name = probe.system_template_uid or "building"
            b_uid = building_location_uid(a_uid, template_name, bx, by)
            building = replace(
                probe,
                location_uid=b_uid,
                parent_location_uid=d_uid,
                world_uid=settlement.world_uid,
                system_location_type=building_system_type,
                is_outdoor=building_is_outdoor,
                created_at=settlement.created_at,
                state_uid=settlement.state_uid,
            )
            buildings.append(building)

            old_levels = list(area.building_layout.levels) if area.building_layout else []
            new_levels: list[LocationLevel] = []
            old_to_new: dict[str, str] = {}
            for lv in old_levels:
                nid = level_uid(b_uid, lv.z)
                old_to_new[lv.level_uid] = nid
                new_levels.append(replace(lv, level_uid=nid, location_uid=b_uid))
            levels_out.extend(new_levels)

            fronts = 0
            passages = area.building_layout.passages if area.building_layout else []
            for passage in passages:
                role = _role_for_passage(passage)
                if role is None:
                    continue
                target = _entry_level(new_levels, old_to_new, passage, building)
                if target is None:
                    continue
                if role == EntryRole.FRONT:
                    fronts += 1
                entries.append(LocationEntryPoint(
                    entry_uid=entry_uid(b_uid, role, passage.passage_uid),
                    location_uid=b_uid,
                    x=passage.to_x,
                    y=passage.to_y,
                    z=target.z,
                    display_name=passage.display_name or role.value,
                    entry_role=role.value,
                    leads_to_level_uid=target.level_uid,
                    entry_difficulty_override=0,
                    guard_level_override=0,
                    is_discovered=True,
                    is_accessible=True,
                ))
            if fronts < 1:
                raise SettlementOutdoorExtractError(
                    f"building {b_uid} has no front entry"
                )

            rebound_cells = [
                replace(c, location_uid=b_uid)
                for c in (area.building_layout.cells if area.building_layout else [])
            ]
            shell = outdoor_shell_wires(rebound_cells)
            small_shells = [
                outdoor_shell_wires(
                    [replace(c, location_uid=b_uid) for c in sl.cells]
                )
                for sl in area.small_layouts
            ]
            area_wires.append(AreaStructureWire(
                area_uid=a_uid,
                slot=AreaSlotWire(
                    cells=list(dict.fromkeys(slot_cells)),
                    ground_z=area_slot.ground_z,
                    facing=area_slot.facing,
                    height=area_slot.height,
                    z_deep=area_slot.z_deep,
                ),
                barrier_cells=cells_to_shell_wires(area.barrier_cells),
                yard_cells=cells_to_shell_wires(area.yard_cells),
                small_layouts=small_shells,
                buildings=[BuildingShellWire(location_uid=b_uid, shell_cells=shell)],
            ))

        district_wires.append(DistrictStructureWire(
            location_uid=d_uid,
            barrier_cells=cells_to_shell_wires(district_layout.barrier_cells),
            areas=area_wires,
        ))

    nodes, edges = collect_connection_graph(
        layout, frozenset({GraphLevel.CITY, GraphLevel.DISTRICT, GraphLevel.AREA}),
    )
    wire = SettlementStructureWire(
        settlement_uid=settlement.location_uid,
        barrier_cells=cells_to_shell_wires(layout.barrier_cells),
        districts=district_wires,
    )
    return ExtractedSettlement(
        districts=districts,
        buildings=buildings,
        levels=levels_out,
        entry_points=entries,
        nodes=nodes,
        edges=edges,
        wire=wire,
    )
