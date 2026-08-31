"""SettlementLayout → SQL rows + pack wire. Pure; no I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayoutExtract import (
    collect_connection_graph,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorShell import (
    cells_to_shell_wires,
    outdoor_shell_wires,
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
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
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


def _type_entry(system_type: str):
    return WorldLocationTypeRegistry.canonical_engine().entry_for(system_type)


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
    district_type = _type_entry("district")
    building_type = _type_entry("building")
    district_is_outdoor = True if district_type is None else bool(district_type.is_outdoor)
    building_is_outdoor = False if building_type is None else bool(building_type.is_outdoor)
    district_system_type = "district" if district_type is None else district_type.system_type
    building_system_type = "building" if building_type is None else building_type.system_type

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
            system_location_subtype=template.district_type,
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
