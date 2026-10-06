"""SettlementLayout → SQL rows + pack wire. Pure; no I/O."""

from __future__ import annotations

from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload

from dataclasses import dataclass, field, replace

from app.application.worldData.generators.assemblers.settlementAssembler.planner.topologyPlan import SettlementTopologyPlan
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
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    building_type_entry,
    district_type_entry,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    area_uid,
    district_location_uid,
)
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.locations.settlement.district.districtTopologySlot import (
    DistrictTopologyEntry,
    DistrictTopologySlot,
)
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.worldPack.settlementStructureWire import (
    AreaSlotWire,
    AreaStructureWire,
    BuildingShellWire,
    BuildingInteriorTransitionsWire,
    DistrictStructureWire,
    SettlementStructureWire,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.application.worldData.transitions.transitionStoragePolicy import BuildingTransitionScope
from app.application.worldData.settlementOutdoor.settlementOutdoorTransitions import project_settlement_transitions


class SettlementOutdoorExtractError(ValueError):
    """Persist-time extract invariant (e.g. missing front door)."""


@dataclass
class ExtractedSettlement:
    districts: list[NamedLocation]
    buildings: list[NamedLocation]
    levels: list[LocationLevel]
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]
    wire: SettlementStructureWire
    sql_transitions: list[Transition] = field(default_factory=list)
    pack_by_building: dict[str, BuildingInteriorTransitionsWire] = field(default_factory=dict)
    transition_context: TransitionRepositoryContext | None = None


@dataclass
class ExtractedTopology:
    districts: list[NamedLocation]
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]
    sql_transitions: list[Transition] = field(default_factory=list)
    pack_by_building: dict[str, BuildingInteriorTransitionsWire] = field(default_factory=dict)
    transition_context: TransitionRepositoryContext | None = None


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


def _district_named_location(
    settlement: NamedLocation,
    slot: DistrictSlot,
    *,
    slot_index: int,
) -> NamedLocation:
    """District NL: drawing key is ``district_topology.template_system_name``, not building FK."""
    district_type = district_type_entry()
    template = slot.district_template
    return NamedLocation(
        location_uid=district_location_uid(
            settlement.world_uid,
            settlement.location_uid, template.system_name, slot_index,
        ),
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
        system_economic_tier=(
            slot.district_ctx.economic_tier
            if slot.district_ctx is not None
            else None
        ),
        location_payload=DistrictPayload(
            district_topology=topology_slot_wire(slot, slot_index=slot_index),
        ).model_dump(mode="json"),
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
    topology: SettlementTopologyPlan,
    *, registry: WorldTransitionTypeRegistry | None = None,
) -> ExtractedTopology:
    districts: list[NamedLocation] = []
    for slot in topology.slots:
        districts.append(
            _district_named_location(settlement, slot, slot_index=slot.slot_index),
        )
    city_nodes, city_edges = _city_topology_graph(topology.nodes, topology.edges)
    context = TransitionRepositoryContext(settlement.world_uid, registry or WorldTransitionTypeRegistry.canonical_engine(),
        {}, {row.location_uid: row for row in [settlement, *districts]}, {row.node_uid: row for row in city_nodes})
    projection = project_settlement_transitions(settlement.world_uid, topology.transitions,
        levels=context.levels, locations=context.locations, nodes=context.nodes,
        building_scopes=[], registry=context.registry)
    return ExtractedTopology(districts=districts, nodes=city_nodes, edges=city_edges,
        sql_transitions=projection.sql_transitions, transition_context=context)


ALL_GRAPH_LEVELS = frozenset({GraphLevel.CITY, GraphLevel.DISTRICT, GraphLevel.AREA})
PACKING_GRAPH_LEVELS = frozenset({GraphLevel.DISTRICT, GraphLevel.AREA})


def extract_settlement(
    settlement: NamedLocation,
    layout: SettlementLayout,
    *,
    graph_levels: frozenset[GraphLevel] | None = None,
    registry: WorldTransitionTypeRegistry | None = None,
) -> ExtractedSettlement:
    building_type = building_type_entry()
    building_is_outdoor = bool(building_type.is_outdoor)
    building_system_type = building_type.system_type

    districts: list[NamedLocation] = []
    buildings: list[NamedLocation] = []
    levels_out: list[LocationLevel] = []
    district_wires: list[DistrictStructureWire] = []
    transitions: list[Transition] = []
    scopes: list[BuildingTransitionScope] = []
    registry = registry or WorldTransitionTypeRegistry.canonical_engine()

    for district_layout in layout.district_layouts:
        slot = district_layout.slot
        district_nl = _district_named_location(
            settlement, slot, slot_index=slot.slot_index,
        )
        d_uid = district_nl.location_uid
        districts.append(district_nl)
        area_wires: list[AreaStructureWire] = []

        for area in district_layout.area_layouts:
            transitions.extend(area.transitions)
            area_slot = area.slot
            slot_cells = list(area_slot.cells)
            if not slot_cells:
                slot_cells = [(0, 0)]
            min_x = min(x for x, _ in slot_cells)
            min_y = min(y for _, y in slot_cells)
            a_uid = area_uid(
                settlement.world_uid, d_uid, min_x, min_y, area_slot.facing,
            )
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
                        deck=area_slot.deck,
                    ),
                    barrier_cells=cells_to_shell_wires(area.barrier_cells),
                    yard_cells=cells_to_shell_wires(area.yard_cells),
                    small_layouts=[],
                    buildings=[],
                ))
                continue

            # The producer already minted the final building and transition UIDs.
            b_uid = probe.location_uid
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
            # Level uid is minted once at structure generation (D3) —
            # extract rebinds the parent column only, never re-mints.
            new_levels = [
                replace(lv, location_uid=b_uid) for lv in old_levels
            ]
            levels_out.extend(new_levels)

            building_transitions = list(area.building_layout.transitions) if area.building_layout else []
            transitions.extend(building_transitions)
            scopes.append(BuildingTransitionScope(b_uid, frozenset(lv.level_uid for lv in new_levels),
                                                  frozenset(item.transition_uid for item in building_transitions)))

            rebound_cells = [
                replace(c, location_uid=b_uid)
                for c in (area.building_layout.cells if area.building_layout else [])
            ]
            shell = cells_to_shell_wires(rebound_cells)
            small_shells = [
                cells_to_shell_wires(
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
                    deck=area_slot.deck,
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
        layout, graph_levels if graph_levels is not None else ALL_GRAPH_LEVELS,
    )
    wire = SettlementStructureWire(
        settlement_uid=settlement.location_uid,
        barrier_cells=cells_to_shell_wires(layout.barrier_cells),
        districts=district_wires,
    )
    context = TransitionRepositoryContext(settlement.world_uid, registry,
        {level.level_uid: level for level in levels_out},
        {row.location_uid: row for row in [settlement, *districts, *buildings]},
        {node.node_uid: node for node in nodes})
    try:
        projection = project_settlement_transitions(settlement.world_uid, transitions,
            levels=context.levels, locations=context.locations, nodes=context.nodes,
            building_scopes=scopes, registry=registry)
    except ValueError as exc:
        raise SettlementOutdoorExtractError(str(exc)) from exc
    payload = wire.model_dump(mode="json")
    for district in payload["districts"]:
        for area in district["areas"]:
            for building in area["buildings"]:
                building["interior_transitions"] = projection.pack_by_building[building["location_uid"]].model_dump(mode="json")
    wire = SettlementStructureWire.model_validate(payload, context={"transition_type_registry": registry})
    return ExtractedSettlement(
        districts=districts,
        buildings=buildings,
        levels=levels_out,
        nodes=nodes,
        edges=edges,
        wire=wire,
        sql_transitions=projection.sql_transitions, pack_by_building=projection.pack_by_building,
        transition_context=context,
    )
