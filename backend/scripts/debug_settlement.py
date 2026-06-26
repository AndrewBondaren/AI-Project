"""Smoke test: SettlementAssembler district + street planning."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")

from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (
    SettlementAssembler,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _run_case(label: str, world: World, settlement: NamedLocation) -> None:
    layout = SettlementAssembler().assemble(world, settlement)
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
    from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (
        SettlementAssembler,
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
    test_city_shared_nodes()


if __name__ == "__main__":
    main()
