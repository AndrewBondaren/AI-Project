"""Smoke test: SettlementAssembler district + street planning."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")

from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (
    SettlementAssembler,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _run_case(label: str, world: World, settlement: NamedLocation, terrain=None) -> None:
    layout = SettlementAssembler().assemble(world, settlement, terrain)
    print(f"=== {label} ===")
    print(f"districts: {len(layout.district_layouts)}")
    for i, dl in enumerate(layout.district_layouts):
        print(
            f"  [{i}] areas={len(dl.area_layouts)} "
            f"district_nodes={len(dl.connection_nodes)} "
            f"district_edges={len(dl.connection_edges)}"
        )
    print(f"city_nodes: {len(layout.connection_nodes)}")
    print(f"city_edges: {len(layout.connection_edges)}")
    print(f"barriers: {len(layout.barrier_cells)}")
    print(f"occupancy: {len(layout.occupancy_cells)}")
    print()


def _shared_boundary_uids(slots, boundary_x: int, sample_y: int) -> set[str]:
    uids: set[str] = set()
    for slot in slots:
        for entry in slot.entry_nodes:
            if entry.role != "through_road":
                continue
            n = entry.node
            if n.x == boundary_x and n.y == sample_y:
                uids.add(n.node_uid)
    return uids


def test_phase_c_placement() -> None:
    """Civic in center (2x2), port only with water, max 1 port, ground_z from terrain."""
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
        plan_district_slots,
    )

    world = World(
        world_uid="world-test-c",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-c",
        world_uid="world-test-c",
        display_name="Coasthold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="city",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    assembler = SettlementAssembler()
    skeleton = assembler._build_skeleton(world, settlement)

    # No water → no port district
    slots_dry = plan_district_slots(world, settlement, skeleton, None)
    assert not any(
        s.district_template.get("district_type") == "port" for s in slots_dry
    ), "port must not appear without adjacent water"

    # Water on north edge of cell (0,1): y = 6000 = origin_y + depth for cell_y=1
    terrain = [
        MapCell(
            world_uid="world-test-c", x=1500, y=6000, z=2,
            system_terrain="liquid_body",
        ),
    ]
    slots_wet = plan_district_slots(world, settlement, skeleton, terrain)
    port_slots = [s for s in slots_wet if s.district_template.get("district_type") == "port"]
    assert len(port_slots) == 1, f"expected 1 port, got {len(port_slots)}"
    assert port_slots[0].ground_z == 0, "port cell has no interior terrain → settlement z"

    # Center cell (1,1) → civic
    civic = next(
        s for s in slots_wet
        if s.origin_x == 3000 and s.origin_y == 3000
    )
    assert civic.district_template.get("system_name") == "civic_center"
    assert len(civic.required_structures) == 1
    print("phase C placement checks: OK")


def test_city_shared_nodes() -> None:
    """2x2 city: adjacent districts share through_road node on internal vertical boundary."""
    world = World(
        world_uid="world-test-2",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-002",
        world_uid="world-test-2",
        display_name="Bighold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="city",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
        plan_district_slots,
    )

    assembler = SettlementAssembler()
    skeleton = assembler._build_skeleton(world, settlement)
    slots = plan_district_slots(world, settlement, skeleton, None)

    assert len(slots) == 4, f"expected 4 districts, got {len(slots)}"

    boundary_x = 3000
    sample_y = 80
    uids = _shared_boundary_uids(slots, boundary_x, sample_y)
    assert len(uids) == 1, (
        f"expected 1 shared node_uid on boundary x={boundary_x} y={sample_y}, got {uids}"
    )

    layout = assembler.assemble(world, settlement)
    city_edges = [e for e in layout.connection_edges if e.graph_level == "city"]
    assert len(city_edges) > 8, "city should have perimeter + internal corridor edges"
    print("city shared-node check: OK")
    _run_case("city 2x2", world, settlement)


def test_phase_e_building_cache() -> None:
    """town_hall: one cache entry, civic district gets area_layout from cache."""
    from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
    from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
        build_layout_cache,
        collect_building_template_names,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
        DEFAULT_DISTRICT_TEMPLATES,
    )

    world = World(
        world_uid="world-test-e",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-e",
        world_uid="world-test-e",
        display_name="Cachehold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    civic = next(t for t in DEFAULT_DISTRICT_TEMPLATES if t["system_name"] == "civic_center")
    slot_a = DistrictSlot(
        origin_x=0, origin_y=0, width_m=3000, depth_m=3000, ground_z=0,
        district_template=civic,
        required_structures=civic.get("required_structures") or [],
    )
    slot_b = DistrictSlot(
        origin_x=3000, origin_y=0, width_m=3000, depth_m=3000, ground_z=0,
        district_template=civic,
        required_structures=civic.get("required_structures") or [],
    )

    assembler = SettlementAssembler()
    skeleton = assembler._build_skeleton(world, settlement)
    names = collect_building_template_names([slot_a, slot_b], world, skeleton)
    assert names == {"town_hall"}

    cache = build_layout_cache(world, skeleton, [slot_a, slot_b], None)
    assert len(cache) == 1
    assert "town_hall" in cache
    fp = cache["town_hall"].occupied_footprint
    assert fp is not None and fp.width >= 4 and fp.depth >= 4

    layout = assembler.assemble(world, settlement)
    civic_layout = layout.district_layouts[0]
    assert len(civic_layout.area_layouts) == 1
    area = civic_layout.area_layouts[0]
    assert area.building_layout.cells
    assert area.building_location.map_x is not None
    print("phase E building cache checks: OK")


def test_phase_area_barriers() -> None:
    """perimeter_barrier on building template → AreaLayout.barrier_cells + layoutCells."""
    from random import Random

    from app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers import (
        should_build_area_barrier,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
        collect_map_cells_from_layout,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
        lookup_building_template,
    )

    assert should_build_area_barrier(
        {"perimeter_barrier": {"template": "stone_fence", "probability": 1.0}},
        Random(0),
    )
    assert not should_build_area_barrier(
        {"perimeter_barrier": {"template": None, "probability": 0}},
        Random(0),
    )

    world = World(
        world_uid="world-test-area",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-area",
        world_uid="world-test-area",
        display_name="Fencehold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    town_hall = lookup_building_template(world, "town_hall")
    assert town_hall is not None
    assert town_hall.get("perimeter_barrier", {}).get("template") == "stone_fence"

    layout = SettlementAssembler().assemble(world, settlement)
    area = layout.district_layouts[0].area_layouts[0]
    assert len(area.barrier_cells) > 0
    assert any(c.system_terrain == "gate" for c in area.barrier_cells)
    assert all(c.location_uid == area.building_location.location_uid for c in area.barrier_cells)

    flat = collect_map_cells_from_layout(world, settlement, layout)
    area_barrier_xy = {(c.x, c.y, c.z) for c in area.barrier_cells}
    assert area_barrier_xy <= {(c.x, c.y, c.z) for c in flat}

    print("phase area barriers checks: OK")


def test_phase_b_travel_and_sidewalk() -> None:
    """road_tier_bonus resolver + per-district has_sidewalk on city entry links."""
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
        DEFAULT_DISTRICT_TEMPLATES,
    )
    from app.application.worldData.generators.road.connectionPolicy import resolve_has_sidewalk
    from app.application.worldData.generators.road.roadTravelResolver import (
        effective_travel_modifier,
        resolve_road_tier_bonus,
    )
    from app.db.models.connectionEdge import ConnectionEdge

    industrial = next(
        t for t in DEFAULT_DISTRICT_TEMPLATES if t["system_name"] == "industrial_quarter"
    )
    civic = next(
        t for t in DEFAULT_DISTRICT_TEMPLATES if t["system_name"] == "civic_center"
    )
    assert resolve_has_sidewalk(industrial) is False
    assert resolve_has_sidewalk(civic) is True

    world = World(
        world_uid="world-test-b",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        economic_tier_registry=[
            {
                "system_tier": "standard",
                "base_value": 2,
                "road_tier_bonus": 1.0,
                "road_tier_durability": 1.0,
            },
            {
                "system_tier": "premium",
                "base_value": 3,
                "road_tier_bonus": 0.95,
                "road_tier_durability": 1.3,
            },
        ],
        material_registry=[
            {
                "system_material": "dirt_road",
                "economic_tier": "premium",
                "structural_strength": 0.3,
                "tags": ["construction"],
                "use_type": ["road"],
            },
        ],
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
    )
    assert resolve_road_tier_bonus(world, "premium") == 0.95

    edge = ConnectionEdge(
        edge_uid="test-edge",
        from_node_uid="a",
        to_node_uid="b",
        connection_type="road",
        graph_level="city",
        world_uid="world-test-b",
        material="dirt_road",
        condition=100,
    )
    assert effective_travel_modifier(world, edge) == 0.95

    settlement = NamedLocation(
        location_uid="city-b",
        world_uid="world-test-b",
        display_name="Roadhold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"
    layout = SettlementAssembler().assemble(world, settlement)
    entry_edges = [e for e in layout.connection_edges if e.edge_uid.startswith("city_link_")]
    assert entry_edges, "town should have city entry link edges"
    for e in entry_edges:
        assert e.has_sidewalk is True, "default civic/residential templates have sidewalk=True"

    print("phase B travel + sidewalk checks: OK")


def test_phase_d_barriers() -> None:
    """Perimeter wall + gates aligned with settlement_gate coords; hamlet has no wall."""
    from random import Random

    from app.application.worldData.generators.assemblers.settlementAssembler.planner.barriers import (
        plan_settlement_barriers,
        should_have_settlement_wall,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        cell_size_m,
        footprint_side_m,
        settlement_origin,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        footprint_gate_coordinates,
    )

    world = World(
        world_uid="world-test-d",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
            {"system_size": "hamlet", "display_size": "Hamlet", "footprint_multiplier": 0.5},
        ],
    )
    assembler = SettlementAssembler()

    hamlet = NamedLocation(
        location_uid="city-d-hamlet",
        world_uid="world-test-d",
        display_name="Hollow",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="hamlet",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    sk_h = assembler._build_skeleton(world, hamlet)
    assert not should_have_settlement_wall(hamlet, sk_h, Random(0))
    assert plan_settlement_barriers(world, hamlet, sk_h, Random(0)) == []

    city = NamedLocation(
        location_uid="city-d-city",
        world_uid="world-test-d",
        display_name="Wallhold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="city",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    city.settlement_density = "medium"
    sk_c = assembler._build_skeleton(world, city)
    rng = Random(f"{world.world_uid}_{city.location_uid}_barriers")
    barriers = plan_settlement_barriers(world, city, sk_c, rng)
    assert len(barriers) > 0

    ox, oy, gz = settlement_origin(city)
    side_m = footprint_side_m(world, sk_c.system_city_size)
    gate_coords = footprint_gate_coordinates(ox, oy, side_m, cell_size_m(world))
    barrier_by_xy = {(c.x, c.y): c for c in barriers}
    assert gate_coords <= set(barrier_by_xy)
    for x, y in gate_coords:
        assert barrier_by_xy[(x, y)].system_terrain == "gate"
    wall_cells = [c for c in barriers if c.system_terrain == "wall"]
    assert wall_cells
    assert all(c.location_uid == city.location_uid for c in barriers)
    assert all(c.z == gz for c in barriers)

    layout = assembler.assemble(world, city)
    assert len(layout.barrier_cells) == len(barriers)
    print("phase D barriers checks: OK")


def test_phase_f_map_occupancy() -> None:
    """Footprint occupancy + collect_map_cells + needs_geometry heuristic."""
    from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
        collect_map_cells_from_layout,
        needs_settlement_geometry,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        footprint_grid_rect,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy import (
        plan_footprint_occupancy_cells,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
        SettlementGeneratorService,
    )

    world = World(
        world_uid="world-test-f",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=[
            {"system_terrain": "urban", "glossary_ref": "terrain_urban"},
            {"system_terrain": "plains", "glossary_ref": "terrain_plains"},
        ],
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
        ],
    )
    town = NamedLocation(
        location_uid="city-f-town",
        world_uid="world-test-f",
        display_name="Foothold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    town.settlement_density = "medium"

    gx0, gy0, gx1, gy1 = footprint_grid_rect(world, town)
    assert (gx0, gy0, gx1, gy1) == (0, 0, 1, 1)

    occ = plan_footprint_occupancy_cells(world, town)
    assert len(occ) == 1
    assert occ[0].location_uid == town.location_uid
    assert occ[0].system_terrain == "urban"

    svc = SettlementGeneratorService()
    assert svc.needs_geometry(town, world, occ) is True

    layout, cells = svc.generate_map_cells(world, town)
    assert len(layout.occupancy_cells) == 1
    assert any(c.system_building_element for c in cells)
    assert svc.needs_geometry(town, world, cells) is False

    city = NamedLocation(
        location_uid="city-f-city",
        world_uid="world-test-f",
        display_name="Gridhold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="city",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    city.settlement_density = "medium"
    assert footprint_grid_rect(world, city) == (0, 0, 2, 2)
    assert len(plan_footprint_occupancy_cells(world, city)) == 4

    print("phase F map occupancy checks: OK")


def test_coordinate_spaces_anchor_3000() -> None:
    """
    NC-1: settlement at map_x=3000 must use grid index 1 and meter origin 3000.
    Smoke at map_x=0 masks mixing grid index with absolute meters.
    """
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
        plan_district_slots,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        cell_size_m,
        footprint_gate_coordinates,
        footprint_grid_rect,
        footprint_meter_rect,
        footprint_side_m,
        settlement_grid_rect,
        settlement_meter_rect,
        settlement_origin,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy import (
        plan_footprint_occupancy_cells,
    )
    from app.application.worldData.generators.coordinates import (
        settlement_origin_m,
    )

    world = World(
        world_uid="world-test-nc1",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
        ],
    )
    town = NamedLocation(
        location_uid="city-nc1-town",
        world_uid="world-test-nc1",
        display_name="Easthold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=3000,
        map_y=0,
        map_z=0,
    )
    town.settlement_density = "medium"

    cell_m = cell_size_m(world)
    assert cell_m == 3000

    origin = settlement_origin_m(town)
    assert (origin.x, origin.y, origin.z) == (3000, 0, 0)
    assert settlement_origin(town) == (3000, 0, 0)

    side_m = footprint_side_m(world, town.system_city_size)
    assert side_m == 3000

    grid_rect = settlement_grid_rect(world, town)
    assert grid_rect.as_tuple() == (1, 0, 2, 1)
    assert footprint_grid_rect(world, town) == (1, 0, 2, 1)

    meter_rect = settlement_meter_rect(world, town)
    assert meter_rect.as_tuple() == (3000, 0, 6000, 3000, 0)
    assert footprint_meter_rect(world, town) == (3000, 0, 6000, 3000, 0)

    gate_coords = footprint_gate_coordinates(3000, 0, side_m, cell_m)
    assert (3000, 0) in gate_coords
    assert (6000, 0) in gate_coords
    assert (3000, 3000) in gate_coords
    assert (6000, 3000) in gate_coords
    assert (0, 0) not in gate_coords
    assert (0, 3000) not in gate_coords

    assembler = SettlementAssembler()
    skeleton = assembler._build_skeleton(world, town)
    slots = plan_district_slots(world, town, skeleton, None)
    assert len(slots) == 1
    assert slots[0].origin_x == 3000
    assert slots[0].origin_y == 0

    occ = plan_footprint_occupancy_cells(world, town)
    assert len(occ) == 1
    assert (occ[0].x, occ[0].y) == (1, 0), "occupancy uses world surface grid index, not meters"

    layout = assembler.assemble(world, town)
    assert layout.connection_nodes, "town should have city connection nodes"
    assert min(n.x for n in layout.connection_nodes) >= 3000
    assert min(n.y for n in layout.connection_nodes) >= 0
    assert max(n.x for n in layout.connection_nodes) <= 6000
    assert max(n.y for n in layout.connection_nodes) <= 3000

    city = NamedLocation(
        location_uid="city-nc1-city",
        world_uid="world-test-nc1",
        display_name="Eastgrid",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="city",
        system_economic_tier="standard",
        map_x=3000,
        map_y=0,
        map_z=0,
    )
    city.settlement_density = "medium"
    assert settlement_grid_rect(world, city).as_tuple() == (1, 0, 3, 2)
    assert settlement_meter_rect(world, city).as_tuple() == (3000, 0, 9000, 6000, 0)

    sk_city = assembler._build_skeleton(world, city)
    city_slots = plan_district_slots(world, city, sk_city, None)
    assert len(city_slots) == 4
    origins = {(s.origin_x, s.origin_y) for s in city_slots}
    assert origins == {
        (3000, 0),
        (6000, 0),
        (3000, 3000),
        (6000, 3000),
    }

    print("coordinate spaces anchor 3000 checks: OK")


def _urban_surface_cells(cells: list[MapCell]) -> set[tuple[int, int]]:
    return {(c.x, c.y) for c in cells if c.system_terrain == "urban"}


def _grid_rect_positions(gx0: int, gy0: int, gx1: int, gy1: int) -> set[tuple[int, int]]:
    return {(gx, gy) for gy in range(gy0, gy1) for gx in range(gx0, gx1)}


def test_phase_3_terrain_footprint() -> None:
    """Terrain urban footprint must match settlement_grid_rect / occupancy (grid index space)."""
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        settlement_grid_rect,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy import (
        plan_footprint_occupancy_cells,
    )
    from app.application.worldData.generators.terrain.terrainGeneratorService import (
        TerrainGeneratorService,
    )

    terrain_reg = [
        {"system_terrain": "urban", "glossary_ref": "terrain_urban"},
        {"system_terrain": "plains", "glossary_ref": "terrain_plains"},
    ]
    size_reg = [
        {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
    ]

    def _city(
        world_uid: str,
        uid: str,
        size: str,
        map_x: int,
        map_y: int = 0,
    ) -> NamedLocation:
        return NamedLocation(
            location_uid=uid,
            world_uid=world_uid,
            display_name=uid,
            system_location_type="city",
            created_at="2026-01-01T00:00:00",
            system_city_size=size,
            system_economic_tier="standard",
            map_x=map_x,
            map_y=map_y,
            map_z=0,
        )

    svc = TerrainGeneratorService()

    world = World(
        world_uid="world-test-terrain",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=terrain_reg,
        city_size_registry=size_reg,
    )
    town_anchor = _city("world-test-terrain", "town-0", "town", 0)
    cells_origin = svc.generate_surface(world, [town_anchor])
    expected_origin = _grid_rect_positions(*settlement_grid_rect(world, town_anchor).as_tuple())
    assert _urban_surface_cells(cells_origin) == expected_origin == {(0, 0)}

    town_east = _city("world-test-terrain", "town-3k", "town", 3000)
    cells_east = svc.generate_surface(world, [town_east])
    expected_east = _grid_rect_positions(*settlement_grid_rect(world, town_east).as_tuple())
    occ_east = {(c.x, c.y) for c in plan_footprint_occupancy_cells(world, town_east)}
    assert _urban_surface_cells(cells_east) == expected_east == occ_east == {(1, 0)}

    city_east = _city("world-test-terrain", "city-3k", "city", 3000)
    cells_city = svc.generate_surface(world, [city_east])
    rect_city = settlement_grid_rect(world, city_east).as_tuple()
    expected_city = _grid_rect_positions(*rect_city)
    assert _urban_surface_cells(cells_city) == expected_city
    assert expected_city == {(1, 0), (2, 0), (1, 1), (2, 1)}

    world_5k = World(
        world_uid="world-test-terrain-5k",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=5000,
        terrain_registry=terrain_reg,
        city_size_registry=size_reg,
    )
    town_5k = _city("world-test-terrain-5k", "town-5k", "town", 5000)
    cells_5k = svc.generate_surface(world_5k, [town_5k])
    assert _urban_surface_cells(cells_5k) == {(1, 0)}

    print("phase 3 terrain footprint checks: OK")


def test_phase_4_collect_map_cells() -> None:
    """Split persist: surface grid occupancy vs meter geometry (Option A)."""
    from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
        collect_geometry_meter_cells,
        collect_map_cells_from_layout,
        collect_surface_grid_cells,
        needs_settlement_geometry,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
        cell_in_footprint_meters,
        footprint_meter_rect,
    )
    from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
        SettlementGeneratorService,
    )

    world = World(
        world_uid="world-test-p4",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-p4",
        world_uid="world-test-p4",
        display_name="Splithold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=3000,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    layout = SettlementAssembler().assemble(world, settlement)
    grid_cells = collect_surface_grid_cells(layout)
    meter_cells = collect_geometry_meter_cells(layout)
    merged = collect_map_cells_from_layout(world, settlement, layout)

    assert grid_cells == layout.occupancy_cells
    assert len(grid_cells) == 1
    assert (grid_cells[0].x, grid_cells[0].y) == (1, 0)
    assert not any(c.system_building_element for c in grid_cells)

    assert len(meter_cells) > 0
    assert any(c.system_building_element for c in meter_cells)
    ox, oy, x1, y1, _ = footprint_meter_rect(world, settlement)
    for c in meter_cells:
        if not c.system_building_element:
            continue
        assert cell_in_footprint_meters(c.x, c.y, ox, oy, x1, y1), (
            f"building cell ({c.x},{c.y}) outside meter footprint"
        )

    assert merged == grid_cells + meter_cells
    assert {id(c) for c in grid_cells}.isdisjoint({id(c) for c in meter_cells})

    svc = SettlementGeneratorService()
    assert needs_settlement_geometry(settlement, world, grid_cells) is True
    assert svc.needs_geometry(settlement, world, merged) is False

    print("phase 4 collect_map_cells checks: OK")


def main() -> None:
    world = World(
        world_uid="world-test",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "radius": 1, "footprint_multiplier": 1.0},
        ],
    )
    settlement = NamedLocation(
        location_uid="city-001",
        world_uid="world-test",
        display_name="Ironhold",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    settlement.settlement_density = "medium"

    _run_case("town 1x1", world, settlement)
    test_phase_c_placement()
    test_phase_b_travel_and_sidewalk()
    test_phase_d_barriers()
    test_phase_e_building_cache()
    test_phase_area_barriers()
    test_phase_f_map_occupancy()
    test_coordinate_spaces_anchor_3000()
    test_phase_3_terrain_footprint()
    test_phase_4_collect_map_cells()
    test_city_shared_nodes()


if __name__ == "__main__":
    main()
