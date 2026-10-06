"""Persist cycle smoke — in-process (path 1) and optional HTTP (path 2).

Path 1: temp SQLite + Container services (no running backend).
Path 2: requires backend on DEBUG_API_URL — start it yourself.
"""
from __future__ import annotations

import asyncio
import json
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
        fine_cells_per_map_cell=64,
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

        from app.application.jsonValidation.worldRow import transition_types
        from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import assemble_building_catalog
        from app.application.worldData.structureTemplateFsImport import load_structure_stdlib
        from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
        from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import extract_settlement
        from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import SettlementOutdoorSqlPersist
        from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
        from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
        from app.application.worldData.pack.io.worldPackReader import WorldPackReader
        from app.application.worldData.pack.read.locationTerritoryVolumes import territory_volume_for_location
        from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository

        structures = StructureCatalog(load_structure_stdlib(Path(__file__).resolve().parents[2] / "structures_templates"))
        catalog = assemble_building_catalog(world, structures=structures)
        # The temporary library must contain the templates referenced by generated NLs.
        await db.conn.executemany("INSERT INTO building_templates(template_uid,system_name,display_name,structure_type,data) "
            "VALUES (?,?,?,?,?)", [(plot.system_name, plot.system_name, plot.display_name, "building",
                                   json.dumps(plot.model_dump(mode="json"))) for plot in catalog.layouts])
        await db.conn.commit()
        layout = SettlementGeneratorService().generate_layout(world, settlement, catalog=catalog)
        registry = transition_types(world)
        extracted = extract_settlement(settlement, layout, registry=registry)
        assert extracted.buildings, "expected building locations"
        assert extracted.sql_transitions, "expected outer transitions"
        persist = SettlementOutdoorSqlPersist(db, container.location_repository(), container.location_level_repository(),
            lambda context: SqliteTransitionRepository(db, context), container.connection_persist_service())
        paths = WorldPackPaths(Path(tmp) / "pack", world.world_uid)
        writer = WorldPackWriter(paths)
        receipt = writer.encode_settlement_structure_tmp(settlement.location_uid, extracted.wire, registry=registry)
        await persist.persist(extracted)
        await persist.persist(extracted)
        writer.publish_settlement_structure(receipt, territory_volume=territory_volume_for_location(world, settlement),
            packed_district_uids=[row.location_uid for row in extracted.districts], structure_status="complete")
        repo = SqliteTransitionRepository(db, extracted.transition_context)
        for item in extracted.sql_transitions:
            assert await repo.get(item.transition_uid) == item
        reader = WorldPackReader(paths)
        for building in extracted.buildings:
            restored = reader.read_building_interior_transitions(settlement.location_uid, building.location_uid, registry=registry)
            assert restored.interior_transitions == extracted.pack_by_building[building.location_uid]
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
        assert first.get("status") == "published", first
        assert first.get("districts", 0) >= 1, first

        children = api_get_location_children(client, world.world_uid, settlement.location_uid)
        assert len(children) > 0

        conn = api_get_connections(client, world.world_uid)
        assert len(conn["edges"]) > 0

        second = api_generate_settlement(client, world.world_uid, settlement.location_uid)
        assert second.get("status") == "skipped", second

    print("persist outdoor HTTP checks: OK")


def main() -> None:
    asyncio.run(test_persist_outdoor_inprocess())
    if "--http" in sys.argv:
        test_persist_outdoor_http()


if __name__ == "__main__":
    main()
