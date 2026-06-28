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

def test_terrain_decoupled_from_settlements() -> None:
    """Terrain must not paint urban or derive climate from cities."""
    from app.application.worldData.generators.terrain.terrainGeneratorService import (
        TerrainGeneratorService,
    )

    terrain_reg = [
        {"system_terrain": "urban", "glossary_ref": "terrain_urban"},
        {"system_terrain": "plains", "glossary_ref": "terrain_plains"},
    ]

    def _surface_cell(cells: list[MapCell], gx: int, gy: int) -> MapCell:
        return next(c for c in cells if c.x == gx and c.y == gy and c.z >= -1)

    svc = TerrainGeneratorService()
    world = World(
        world_uid="world-test-terrain",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=terrain_reg,
        default_climate_zone="temperate",
    )
    region = NamedLocation(
        location_uid="region-north",
        world_uid=world.world_uid,
        display_name="North",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="arctic",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    city_a = NamedLocation(
        location_uid="city-a",
        world_uid=world.world_uid,
        display_name="City A",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        parent_location_uid=region.location_uid,
        system_city_size="town",
        map_x=3000,
        map_y=0,
        map_z=0,
    )

    cells_one_city = svc.generate_surface(world, [region, city_a])
    assert _urban_surface_cells(cells_one_city) == set()
    cell_1_0_one = _surface_cell(cells_one_city, 1, 0)
    assert cell_1_0_one.system_terrain == "plains"
    assert cell_1_0_one.location_uid == region.location_uid
    assert cell_1_0_one.temperature_base <= -20
    assert cell_1_0_one.rainfall == 0  # arctic + water: below cool_temp

    city_b = NamedLocation(
        location_uid="city-b",
        world_uid=world.world_uid,
        display_name="City B",
        system_location_type="city",
        created_at="2026-01-01T00:00:00",
        parent_location_uid=region.location_uid,
        system_city_size="city",
        map_x=9000,
        map_y=0,
        map_z=0,
    )
    cells_two_cities = svc.generate_surface(world, [region, city_a, city_b])
    cell_1_0_two = _surface_cell(cells_two_cities, 1, 0)
    assert cell_1_0_two.temperature_base == cell_1_0_one.temperature_base
    assert cell_1_0_two.location_uid == region.location_uid

    print("terrain decoupled from settlements checks: OK")


def test_climate_zone_voronoi() -> None:
    """Climate at grid cell follows nearest zone anchor, not cities."""
    from app.application.worldData.generators.climate import ClimateGeneratorService

    svc = ClimateGeneratorService()
    world = World(
        world_uid="world-test-climate-voronoi",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        default_climate_zone="temperate",
    )
    region = NamedLocation(
        location_uid="region-north",
        world_uid=world.world_uid,
        display_name="North",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="arctic",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    uid_map = {region.location_uid: region}
    field = svc.build_zone_field(world, [region], 3000)
    sample = svc.sample_at_grid(world, uid_map, field, 5, 0)
    assert sample.system_climate_zone == "arctic"
    assert sample.zone_location_uid == region.location_uid
    assert sample.typical_elevation_z == 4

    print("climate zone voronoi checks: OK")


def test_climate_registry_override() -> None:
    """world.climate_zone_registry overrides enum defaults."""
    from app.application.worldData.generators.climate.registry import profile_for

    world = World(
        world_uid="world-test-climate-registry",
        name="Test",
        created_at="2026-01-01T00:00:00",
        climate_zone_registry=[
            {
                "system_climate": "arctic",
                "base_temperature": -40,
                "base_rainfall": 5,
            },
        ],
    )
    profile = profile_for(world, "arctic")
    assert profile.base_temperature == -40
    assert profile.base_rainfall == 5
    assert profile.typical_elevation_z == 4

    print("climate registry override checks: OK")


def test_climate_temperature_formula() -> None:
    """temperature_base = base_temperature - lapse × (z / 100)."""
    from app.application.worldData.generators.climate import ClimateGeneratorService

    svc = ClimateGeneratorService()
    world = World(
        world_uid="world-test-climate-formula",
        name="Test",
        created_at="2026-01-01T00:00:00",
        elevation_lapse_rate=0.65,
    )
    temp, rainfall = svc.weather_at_elevation(world, "arctic", 1000)
    assert temp == -32
    assert rainfall == 0

    temp_t, rain_t = svc.weather_at_elevation(world, "temperate", 0)
    assert rain_t == 55

    print("climate temperature formula checks: OK")


def test_climate_manual_anchor_voronoi() -> None:
    """Manual climate_anchor wins over admin region in Voronoi."""
    from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService

    world = World(
        world_uid="world-test-climate-manual",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=[{"system_terrain": "plains", "glossary_ref": "terrain_plains"}],
        default_climate_zone="temperate",
    )
    region = NamedLocation(
        location_uid="region-temp",
        world_uid=world.world_uid,
        display_name="Region",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="temperate",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    peak = NamedLocation(
        location_uid="anchor-arctic-peak",
        world_uid=world.world_uid,
        display_name="Peak",
        system_location_type="climate_anchor",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="arctic",
        map_x=9000,
        map_y=0,
        map_z=4000,
    )
    orch = ClimateOrchestratorService()
    cells = orch.full_surface(world, [region, peak])
    cell_at_peak = next(c for c in cells if c.x == 3 and c.y == 0)
    assert cell_at_peak.location_uid == peak.location_uid
    assert cell_at_peak.rainfall == 0

    print("climate manual anchor voronoi checks: OK")


def test_climate_orchestrator_passes() -> None:
    """Orchestrator allows entry at pass level (DAG hook points)."""
    from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService

    world = World(
        world_uid="world-test-orchestrator",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=[{"system_terrain": "plains", "glossary_ref": "terrain_plains"}],
    )
    region = NamedLocation(
        location_uid="region-o",
        world_uid=world.world_uid,
        display_name="R",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="temperate",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    orch = ClimateOrchestratorService()
    heightmap = orch.heightmap_only(world, [region])
    assert all(c.temperature_base is None for c in heightmap)
    surface = orch.apply_weather_only(world, [region], heightmap)
    assert all(c.temperature_base is not None for c in surface)

    print("climate orchestrator passes checks: OK")


def test_climate_detect_relative_elevation() -> None:
    """Auto anchors: terrain features only; zone from pole field, not elevation."""
    from app.application.worldData.generators.climate.anchorAssign import auto_anchors_from_features
    from app.application.worldData.generators.climate.anchorDetect import detect_terrain_features
    from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
    from app.application.worldData.generators.climate.poleResolve import resolve_pole_field
    from app.db.models.world import World

    world_uid = "world-test-detect"
    world = World(
        world_uid=world_uid,
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        climate_pole_preset="desert",
        default_climate_zone="desert",
    )
    bbox = GridBBox(0, 4, 0, 4)
    pole_field = resolve_pole_field(world, [], 3000, bbox)

    def _cell(gx: int, gy: int, z: int, terrain: str = "plains") -> MapCell:
        return MapCell(
            world_uid=world_uid, x=gx, y=gy, z=z, system_terrain=terrain,
        )

    plateau = [_cell(0, 0, 3200), _cell(1, 0, 3200), _cell(0, 1, 3200), _cell(1, 1, 3200)]
    assert detect_terrain_features(plateau) == []

    peak_row = plateau + [_cell(2, 0, 3400), _cell(2, 1, 3200), _cell(3, 0, 3200)]
    features = detect_terrain_features(peak_row)
    assert len(features) == 1
    assert features[0].gx == 2 and features[0].gy == 0

    auto = auto_anchors_from_features(features, world, {}, pole_field)
    assert len(auto) == 1
    assert auto[0].system_climate_zone == "desert"

    gorge = [
        _cell(0, 0, 3000), _cell(1, 0, 3000), _cell(2, 0, 3000),
        _cell(0, 1, 3000), _cell(1, 1, 2850), _cell(2, 1, 3000),
        _cell(0, 2, 3000), _cell(1, 2, 3000), _cell(2, 2, 3000),
    ]
    gorge_auto = auto_anchors_from_features(
        detect_terrain_features(gorge), world, {}, pole_field,
    )
    assert len(gorge_auto) == 1
    assert gorge_auto[0].system_climate_zone == "desert"

    lake = [
        _cell(0, 0, 3000), _cell(1, 0, 3000),
        _cell(0, 1, 3000), _cell(1, 1, 2990, "liquid_body"),
    ]
    lake_auto = auto_anchors_from_features(
        detect_terrain_features(lake), world, {}, pole_field,
    )
    assert len(lake_auto) == 1

    print("climate detect relative elevation checks: OK")


def test_climate_pole_tier() -> None:
    """Pole field: N=1 fade, derived temp from peak bounds, manual climate_pole."""
    from app.application.worldData.generators.climate import ClimateGeneratorService
    from app.application.worldData.generators.climate.climatePoleField import GridBBox
    from app.application.worldData.generators.climate.poleResolve import (
        derived_pole_temperature,
        resolve_pole_field,
    )
    from app.application.worldData.generators.climate.climatePole import PoleKind

    assert derived_pole_temperature(PoleKind.COLD, -40, 45) == -23
    assert derived_pole_temperature(PoleKind.HOT, -40, 45) == 28

    world = World(
        world_uid="world-test-pole",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        climate_temperature_peak_min=-40,
        climate_temperature_peak_max=45,
        climate_pole_preset="ice",
        default_climate_zone="temperate",
    )
    region = NamedLocation(
        location_uid="region-pole",
        world_uid=world.world_uid,
        display_name="R",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="temperate",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    bbox = GridBBox(-2, 2, -2, 2)
    field = resolve_pole_field(world, [region], 3000, bbox)
    assert len(field.poles) == 1
    assert field.poles[0].system_climate_zone == "arctic"

    svc = ClimateGeneratorService()
    pole = field.poles[0]
    assert pole.base_temperature == -23
    at_pole = svc.sample_at_pole_field(world, field, pole.gx, pole.gy)
    assert at_pole.base_temperature_override == -23
    assert at_pole.system_climate_zone == "arctic"

    pole_loc = NamedLocation(
        location_uid="pole-manual",
        world_uid=world.world_uid,
        display_name="Cold pole",
        system_location_type="climate_pole",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="arctic",
        system_location_subtype="cold",
        map_x=0,
        map_y=9000,
        map_z=0,
    )
    manual_field = resolve_pole_field(world, [region, pole_loc], 3000, bbox)
    assert len(manual_field.poles) == 1
    assert manual_field.poles[0].location_uid == pole_loc.location_uid

    print("climate pole tier checks: OK")


def test_climate_pole_mode_manual() -> None:
    """CL-4: climate_pole_mode=manual without pole → empty field, no autoresolve."""
    from app.application.worldData.generators.climate.climatePole import PoleMode
    from app.application.worldData.generators.climate.climatePoleField import GridBBox
    from app.application.worldData.generators.climate.poleResolve import resolve_pole_field

    world = World(
        world_uid="world-test-pole-manual",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        climate_pole_mode=PoleMode.MANUAL,
        climate_pole_preset="ice",
    )
    region = NamedLocation(
        location_uid="region-manual",
        world_uid=world.world_uid,
        display_name="R",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="desert",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    bbox = GridBBox(-2, 2, -2, 2)
    field = resolve_pole_field(world, [region], 3000, bbox)
    assert field.is_empty()

    world_auto = World(
        world_uid="world-test-pole-auto",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        climate_pole_mode=PoleMode.AUTORESOLVE,
        climate_pole_preset="ice",
    )
    field_auto = resolve_pole_field(world_auto, [region], 3000, bbox)
    assert len(field_auto.poles) == 1

    print("climate pole mode manual checks: OK")


def test_climate_admin_merge_skipped_with_pole() -> None:
    """CL-2b: admin zones not merged into local_field when pole tier active."""
    from app.application.worldData.generators.assemblers.climateAssembler.passes.anchorCollectPass import (
        run_anchor_collect_pass,
    )
    from app.application.worldData.generators.climate.poleResolve import resolve_pole_field
    from app.application.worldData.generators.coordinates import cell_size_m

    world = World(
        world_uid="world-test-admin-skip",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        climate_pole_preset="ice",
        terrain_registry=[{"system_terrain": "plains", "glossary_ref": "terrain_plains"}],
    )
    region = NamedLocation(
        location_uid="region-admin",
        world_uid=world.world_uid,
        display_name="R",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="desert",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    from app.application.worldData.generators.assemblers.climateAssembler.passes.heightmapPass import (
        grid_bbox_from_locations,
        run_heightmap_pass,
    )

    cell_m     = cell_size_m(world)
    bbox       = grid_bbox_from_locations([region], cell_m, 2)
    pole_field = resolve_pole_field(world, [region], cell_m, bbox)
    heightmap  = run_heightmap_pass(world, [region], pole_field, 2)
    field      = run_anchor_collect_pass(world, [region], heightmap, pole_field)

    assert not pole_field.is_empty()
    assert field.is_empty()

    pole_empty = resolve_pole_field(
        World(
            world_uid="world-test-admin-fallback",
            name="Test",
            created_at="2026-01-01T00:00:00",
            map_cell_size_m=3000,
            climate_pole_mode="manual",
        ),
        [region],
        cell_m,
        bbox,
    )
    field_legacy = run_anchor_collect_pass(world, [region], heightmap, pole_empty)
    assert len(field_legacy.anchors) == 1
    assert field_legacy.anchors[0].source.value == "admin"

    print("climate admin merge skip checks: OK")


def test_climate_tier_resolve() -> None:
    """CL-2: pole base + local override in world-relative radius; admin ignored."""
    from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService

    world = World(
        world_uid="world-test-tier",
        name="Test",
        created_at="2026-01-01T00:00:00",
        map_cell_size_m=3000,
        terrain_registry=[{"system_terrain": "plains", "glossary_ref": "terrain_plains"}],
        climate_pole_preset="binary",
        climate_local_influence_fraction=0.25,
        default_climate_zone="temperate",
    )
    region = NamedLocation(
        location_uid="region-tier",
        world_uid=world.world_uid,
        display_name="Region",
        system_location_type="region",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="desert",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    peak = NamedLocation(
        location_uid="anchor-tier-peak",
        world_uid=world.world_uid,
        display_name="Peak",
        system_location_type="climate_anchor",
        created_at="2026-01-01T00:00:00",
        system_climate_zone="arctic",
        map_x=9000,
        map_y=0,
        map_z=4000,
    )
    orch = ClimateOrchestratorService()
    cells = orch.full_surface(world, [region, peak])
    cell_peak = next(c for c in cells if c.x == 3 and c.y == 0)
    cell_far  = next(c for c in cells if c.x == -2 and c.y == 0)

    assert cell_peak.location_uid == peak.location_uid
    assert cell_peak.rainfall == 0
    assert cell_far.location_uid is None
    assert cell_peak.temperature_base < cell_far.temperature_base

    print("climate tier resolve checks: OK")


def test_climate_precipitation_liquid() -> None:
    """CL-15: rainfall = moisture × liquid phase band; peak clamp."""
    from app.application.worldData.generators.climate import ClimateGeneratorService
    from app.application.worldData.generators.climate.precipitation import (
        effective_rainfall,
        liquid_precipitation_mult,
        resolve_world_precipitation_liquid,
    )

    water_world = World(
        world_uid="world-test-precip",
        name="Test",
        created_at="2026-01-01T00:00:00",
        material_registry=[
            {
                "system_material": "water",
                "material_category": "liquid",
                "cool_into": "ice",
                "cool_temp": 0,
                "heat_into": "steam",
                "heat_temp": 100,
            },
        ],
    )
    liquid = resolve_world_precipitation_liquid(water_world)
    assert liquid["system_material"] == "water"
    assert liquid_precipitation_mult(15, liquid) == 1.0
    assert liquid_precipitation_mult(-10, liquid) == 0.0
    assert effective_rainfall(55, 15, water_world) == 55
    assert effective_rainfall(55, -10, water_world) == 0

    cold_world = World(
        world_uid="world-test-precip-cold",
        name="Test",
        created_at="2026-01-01T00:00:00",
        climate_temperature_peak_min=-60,
        climate_temperature_peak_max=35,
        climate_zone_registry=[
            {"system_climate": "arctic", "base_temperature": -55, "base_rainfall": 20},
        ],
        material_registry=water_world.material_registry,
    )
    svc = ClimateGeneratorService()
    temp, rain = svc.weather_at_elevation(cold_world, "arctic", 0)
    assert temp == -55
    assert rain == 0

    ammonia_world = World(
        world_uid="world-test-precip-ammonia",
        name="Test",
        created_at="2026-01-01T00:00:00",
        precipitation_liquid="ammonia",
        material_registry=[
            {
                "system_material": "ammonia",
                "material_category": "liquid",
                "cool_into": "ice",
                "cool_temp": -80,
                "heat_into": "gas",
                "heat_temp": -30,
            },
        ],
    )
    assert effective_rainfall(40, -55, ammonia_world) == 40

    peak_world = World(
        world_uid="world-test-peak-clamp",
        name="Test",
        created_at="2026-01-01T00:00:00",
        climate_temperature_peak_min=-60,
        climate_temperature_peak_max=45,
        climate_zone_registry=[
            {"system_climate": "arctic", "base_temperature": -100, "base_rainfall": 5},
        ],
    )
    temp_clamped, _ = svc.weather_at_elevation(peak_world, "arctic", 0)
    assert temp_clamped == -60

    print("climate precipitation liquid checks: OK")


def test_climate_logging_warnings() -> None:
    """Logging: warn_once on fallbacks; debug_once on peak clamp."""
    import logging
    from io import StringIO

    from app.application.worldData.generators.climate import ClimateGeneratorService
    from app.application.worldData.generators.climate.climatePole import PoleMode
    from app.application.worldData.generators.climate.loggingHelpers import _debugged, _warned
    from app.application.worldData.generators.climate.poleResolve import resolve_pole_field
    from app.application.worldData.generators.climate.registry import profile_for

    _warned.clear()
    _debugged.clear()

    warn_buf = StringIO()
    warn_handler = logging.StreamHandler(warn_buf)
    warn_handler.setLevel(logging.WARNING)
    climate_log = logging.getLogger("app.application.worldData.generators.climate")
    climate_log.addHandler(warn_handler)
    climate_log.setLevel(logging.WARNING)

    resolve_pole_field(
        World(
            world_uid="world-log-manual",
            name="Test",
            created_at="2026-01-01T00:00:00",
            climate_pole_mode=PoleMode.MANUAL,
        ),
        [],
        3000,
        None,
    )
    profile_for(
        World(world_uid="world-log-unknown", name="Test", created_at="2026-01-01T00:00:00"),
        "not_a_real_climate_zone",
    )
    resolve_pole_field(
        World(
            world_uid="world-log-pole-bad",
            name="Test",
            created_at="2026-01-01T00:00:00",
            map_cell_size_m=3000,
        ),
        [
            NamedLocation(
                location_uid="pole-bad",
                world_uid="world-log-pole-bad",
                display_name="Bad",
                system_location_type="climate_pole",
                created_at="2026-01-01T00:00:00",
                map_x=0,
                map_y=0,
                map_z=0,
            ),
        ],
        3000,
        None,
    )

    warn_out = warn_buf.getvalue()
    assert "mode=manual" in warn_out
    assert "unknown system_climate=not_a_real_climate_zone" in warn_out
    assert "no system_climate_zone" in warn_out
    climate_log.removeHandler(warn_handler)

    _debugged.clear()
    debug_buf = StringIO()
    debug_handler = logging.StreamHandler(debug_buf)
    debug_handler.setLevel(logging.DEBUG)
    helpers_log = logging.getLogger("app.application.worldData.generators.climate.loggingHelpers")
    helpers_log.addHandler(debug_handler)
    helpers_log.setLevel(logging.DEBUG)

    svc = ClimateGeneratorService()
    temp, _ = svc.weather_at_elevation(
        World(
            world_uid="world-log-clamp",
            name="Test",
            created_at="2026-01-01T00:00:00",
            climate_temperature_peak_min=-60,
            climate_temperature_peak_max=45,
            climate_zone_registry=[
                {"system_climate": "arctic", "base_temperature": -100, "base_rainfall": 5},
            ],
        ),
        "arctic",
        0,
    )
    assert temp == -60
    assert "temperature clamp" in debug_buf.getvalue()
    helpers_log.removeHandler(debug_handler)

    print("climate logging warnings checks: OK")


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
    test_terrain_decoupled_from_settlements()
    test_climate_zone_voronoi()
    test_climate_registry_override()
    test_climate_temperature_formula()
    test_climate_manual_anchor_voronoi()
    test_climate_orchestrator_passes()
    test_climate_detect_relative_elevation()
    test_climate_pole_tier()
    test_climate_pole_mode_manual()
    test_climate_admin_merge_skipped_with_pole()
    test_climate_tier_resolve()
    test_climate_precipitation_liquid()
    test_climate_logging_warnings()
    test_phase_4_collect_map_cells()
    test_city_shared_nodes()


if __name__ == "__main__":
    main()
