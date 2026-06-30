"""Persist cycle smoke — in-process (path 1) and optional HTTP (path 2).

Path 1: temp SQLite + Container services (no running backend).
Path 2: requires backend on DEBUG_API_URL — start it yourself.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.core.container import Container
from app.core.configManager import ConfigManager
from app.db.database import Database
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _test_world() -> World:
    return World(
        world_uid="world-persist-smoke",
        name="Persist Smoke",
        created_at="2026-06-26T00:00:00",
        map_cell_size_m=3000,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
        terrain_registry=[
            {"system_terrain": "urban", "glossary_ref": "terrain_urban"},
            {"system_terrain": "plains", "glossary_ref": "terrain_plains"},
        ],
    )


def _test_settlement(world_uid: str) -> NamedLocation:
    loc = NamedLocation(
        location_uid="city-persist-smoke",
        world_uid=world_uid,
        display_name="Smokehold",
        system_location_type="city",
        created_at="2026-06-26T00:00:00",
        system_city_size="town",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    loc.settlement_density = "medium"
    return loc


async def test_persist_outdoor_inprocess() -> None:
    from app.db.models.connectionEdge import ConnectionEdge
    from app.db.models.connectionEdgeCell import ConnectionEdgeCell
    from app.db.models.connectionNode import ConnectionNode

    db: Database | None = None
    tmp = tempfile.mkdtemp()
    try:
        db_path = str(Path(tmp) / "smoke.db")
        db = Database(path=db_path)
        await db.connect()
        await db.apply_migrations()
        await db.validate_schema([ConnectionNode, ConnectionEdge, ConnectionEdgeCell])

        container = Container(config_manager=ConfigManager(), db=db)
        world = _test_world()
        settlement = _test_settlement(world.world_uid)

        await container.world_repository().create(world)
        await container.location_repository().create(settlement)

        generator = SettlementGeneratorService()
        layout = generator.generate_layout(world, settlement)

        persist = container.settlement_persist_service()
        result = await persist.persist_outdoor(world, settlement, layout)

        assert result.scopes_applied, f"expected scopes applied, got {result}"
        assert result.map_cells.succeeded > 0, "expected map cells persisted"

        children = await container.location_repository().get_children(settlement.location_uid)
        assert len(children) > 0, "expected building locations persisted"

        edges = await container.connection_edge_repository().get_by_world(world.world_uid)
        city_edges = [e for e in edges if e.graph_level == "city"]
        district_edges = [e for e in edges if e.graph_level == "district"]
        assert len(city_edges) > 0, "expected city connection edges"
        assert len(district_edges) > 0, "expected district connection edges"

        repeat = await persist.persist_outdoor(world, settlement, layout)
        assert repeat.scopes_skipped, "repeat outdoor persist should skip"
        assert repeat.buildings.succeeded == 0, "buildings should not duplicate"
    finally:
        if db is not None:
            await db.disconnect()
        shutil.rmtree(tmp, ignore_errors=True)

    print("persist outdoor in-process checks: OK")


def test_persist_outdoor_http() -> None:
    from debug_api_helpers import (
        api_client,
        api_generate_settlement,
        api_get_connections,
        api_get_location_children,
        api_reset_world,
    )

    world = _test_world()
    settlement = _test_settlement(world.world_uid)

    with api_client() as client:
        api_reset_world(client, world, [settlement])
        first = api_generate_settlement(client, world.world_uid, settlement.location_uid)
        assert first["scopes_applied"], first
        assert first.get("dominant_material"), "expected dominant_material in response"

        children = api_get_location_children(client, world.world_uid, settlement.location_uid)
        assert len(children) > 0

        conn = api_get_connections(client, world.world_uid)
        assert len(conn["edges"]) > 0

        second = api_generate_settlement(client, world.world_uid, settlement.location_uid)
        assert second.get("scopes_skipped"), second

    print("persist outdoor HTTP checks: OK")


def main() -> None:
    asyncio.run(test_persist_outdoor_inprocess())
    if "--http" in sys.argv:
        test_persist_outdoor_http()


if __name__ == "__main__":
    main()
