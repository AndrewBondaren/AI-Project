"""Extract persist payloads from SettlementLayout."""

from __future__ import annotations

from dataclasses import replace

from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
    needs_settlement_geometry,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionEdgeCell import ConnectionEdgeCell
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def collect_connection_graph(
    layout: SettlementLayout,
    graph_levels: frozenset[GraphLevel],
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    nodes: list[ConnectionNode] = []
    edges: list[ConnectionEdge] = []

    if GraphLevel.CITY in graph_levels:
        nodes.extend(layout.connection_nodes)
        edges.extend(layout.connection_edges)

    for district in layout.district_layouts:
        if GraphLevel.DISTRICT in graph_levels:
            nodes.extend(district.connection_nodes)
            edges.extend(district.connection_edges)

    return nodes, edges


def collect_edge_cells(_layout: SettlementLayout) -> list[ConnectionEdgeCell]:
    """Road bed cells along edges — not populated by generators yet."""
    return []


def collect_building_locations(
    layout: SettlementLayout,
    settlement: NamedLocation,
) -> list[NamedLocation]:
    buildings: list[NamedLocation] = []
    for district in layout.district_layouts:
        for area in district.area_layouts:
            building = area.building_location
            buildings.append(replace(
                building,
                parent_location_uid=settlement.location_uid,
            ))
    return buildings


def needs_settlement_outdoor_persist(
    settlement:         NamedLocation,
    world:              World,
    existing_cells:     list[MapCell],
    existing_children:  list[NamedLocation],
    existing_city_edges: list[ConnectionEdge],
) -> bool:
    if needs_settlement_geometry(settlement, world, existing_cells):
        return True
    if not existing_children:
        return True
    if not existing_city_edges:
        return True
    return False
