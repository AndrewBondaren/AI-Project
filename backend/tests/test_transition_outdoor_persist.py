"""G3 production materialize caller against temporary SQL and pack storage."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.application.worldData.connectionPersistService import ConnectionPersistService
from app.application.worldData.generators.assemblers.settlementAssembler.timings import SettlementAssembleTimings
from app.application.worldData.generators.structure.physicalTransition import physical_transition
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import extract_settlement, extract_topology
from app.application.worldData.settlementOutdoor.settlementOutdoorPackingJob import DistrictPackContext, SettlementOutdoorPackingJob
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import SettlementOutdoorSqlPersist
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import district_location_uid
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import WallClock
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.db.database import Database
from app.db.models.connectionNode import ConnectionNode
from app.db.models.world import World
from app.db.repositories.sqlite.connectionNodeRepository import SqliteConnectionNodeRepository
from app.db.repositories.sqlite.connectionEdgeRepository import SqliteConnectionEdgeRepository
from app.db.repositories.sqlite.connectionEdgeCellRepository import SqliteConnectionEdgeCellRepository
from app.db.repositories.sqlite.namedLocationRepository import SqliteNamedLocationRepository
from app.db.repositories.sqlite.locationLevelRepository import SqliteLocationLevelRepository
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from tests.test_settlement_outdoor_extract import _layout, _settlement
from app.application.worldData.generators.assemblers.settlementAssembler.planner.topologyPlan import SettlementTopologyPlan


class TransitionOutdoorPersistTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "world.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        self.world = World("w1", "Outdoor", "2026-10-06")
        await self.db.conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES (?,?,?)",
                                   (self.world.world_uid, self.world.name, self.world.created_at))
        await self.db.conn.commit()
        await self.db.conn.execute("INSERT INTO building_templates(template_uid,system_name,display_name,structure_type,data) "
                                   "VALUES ('hut','hut','Hut','building','{}')")
        await self.db.conn.commit()
        self.settlement = _settlement()
        self.locations = SqliteNamedLocationRepository(self.db)
        await self.locations.create(self.settlement)
        self.nodes = SqliteConnectionNodeRepository(self.db)
        self.edges = SqliteConnectionEdgeRepository(self.db)
        self.persist = SettlementOutdoorSqlPersist(self.db, self.locations,
            SqliteLocationLevelRepository(self.db), lambda context: SqliteTransitionRepository(self.db, context),
            ConnectionPersistService(self.nodes, self.edges, SqliteConnectionEdgeCellRepository(self.db)))
        endpoint = TransitionEndpoint(space="level", level_uid="old-level", x=1, y=0, z=0)
        main = physical_transition("w1", TransitionType.MAIN_ENTRANCE,
            TransitionEndpoint(x=0, y=0, z=0, node_uid="entry-node"), endpoint, "probe-hut-0-0")
        door = physical_transition("w1", TransitionType.DOORWAY, endpoint,
            endpoint.model_copy(update={"x": 2}), "probe-hut-0-0")
        self.layout = _layout(passages=[main, door])
        self.layout.district_layouts[0].area_layouts[0].connection_nodes = [
            ConnectionNode("entry-node", 0, 0, 0, "building_entrance", "area", "w1")]
        self.paths = WorldPackPaths(Path(self.tmp.name) / "pack", "w1")
        writer = WorldPackWriter(self.paths)
        slot = self.layout.district_layouts[0].slot
        district_uid = district_location_uid("w1", "set-1", "core", slot.slot_index)
        self.ctx = DistrictPackContext(self.world, self.settlement, Mock(), writer,
            TerritoryVolume(x0=-10, y0=-10, z0=-1, x1=20, y1=20, z1=10), None, Mock(),
            ([], []), slot, district_uid, [district_uid], WallClock(), SettlementAssembleTimings())
        self.generator = Mock()
        self.generator.generate_layout.return_value = self.layout
        self.invalidate = Mock()
        self.job = SettlementOutdoorPackingJob(self.generator, self.persist, self.invalidate,
            Mock(), Mock(), self.nodes, self.edges, self.locations)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    async def counts(self):
        async with self.db.conn.execute("SELECT (SELECT count(*) FROM transitions), "
                "(SELECT count(*) FROM transition_sides)") as cursor:
            return tuple(await cursor.fetchone())

    async def test_materialize_repeat_preserves_crud_and_pack_partition(self):
        result, nbytes, _ = await self.job.materialize_district(self.ctx)
        self.assertEqual((result.buildings, result.levels, result.entry_points), (1, 1, 1))
        self.assertGreater(nbytes, 0)
        self.assertEqual(await self.counts(), (1, 2))
        extracted = extract_settlement(self.settlement, self.layout)
        repo = SqliteTransitionRepository(self.db, extracted.transition_context)
        main = extracted.sql_transitions[0]
        modified = await repo.update(main.transition_uid, {"is_active": False,
            "destination_side": {"is_discovered": False, "is_accessible": False, "entry_difficulty_override": 0}})
        await self.job.materialize_district(self.ctx)
        self.assertEqual(await repo.get(main.transition_uid), modified)
        self.assertEqual(await self.counts(), (1, 2))
        restored = WorldPackReader(self.paths).read_building_interior_transitions(
            "set-1", "probe-hut-0-0", registry=extracted.transition_context.registry)
        self.assertEqual(restored.interior_transitions, extracted.pack_by_building["probe-hut-0-0"])
        self.assertEqual(len(restored.interior_transitions.transitions), 1)
        self.assertIsNone(await repo.get(restored.interior_transitions.transitions[0].transition_uid))
        self.assertIsNotNone(await self.nodes.get_by_id("entry-node"))
        self.assertEqual(self.invalidate.call_count, 2)

    async def test_changed_geometry_adds_uid_without_removing_old_aggregate(self):
        await self.job.materialize_district(self.ctx)
        building = self.layout.district_layouts[0].area_layouts[0].building_layout
        old = building.transitions[0]
        building.transitions[0] = physical_transition("w1", TransitionType.MAIN_ENTRANCE,
            old.source, old.destination.model_copy(update={"x": 3}), "probe-hut-0-0")
        await self.job.materialize_district(self.ctx)
        self.assertEqual(await self.counts(), (2, 4))
        repo = SqliteTransitionRepository(self.db, extract_settlement(self.settlement, self.layout).transition_context)
        self.assertEqual(await repo.get(old.transition_uid), old)

    async def test_world_custom_types_reach_sql_and_pack(self):
        self.world.transition_type_registry = [
            *WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
            {"system_type": "custom_main", "display_name": "Main", "behaves_as": "main_entrance"},
            {"system_type": "custom_doorway", "display_name": "Doorway", "behaves_as": "doorway"},
        ]
        registry = WorldTransitionTypeRegistry.model_validate(self.world.transition_type_registry)
        building = self.layout.district_layouts[0].area_layouts[0].building_layout
        for index, item in enumerate(building.transitions):
            wire = item.model_dump(mode="json")
            wire["system_transition_type"] = "custom_main" if index == 0 else "custom_doorway"
            wire["destination_side"].update(is_discovered=False, entry_difficulty_override=0)
            item = Transition.model_validate(wire, context={"transition_type_registry": registry})
            building.transitions[index] = item.model_copy(update={"transition_uid": transition_uid(
                item.world_uid, item.system_transition_type, item.source, item.destination)})
        result, _, _ = await self.job.materialize_district(self.ctx)
        self.assertEqual(result.entry_points, 1)
        extracted = extract_settlement(self.settlement, self.layout, registry=registry)
        repo = SqliteTransitionRepository(self.db, extracted.transition_context)
        self.assertEqual(await repo.get(building.transitions[0].transition_uid), building.transitions[0])
        restored = WorldPackReader(self.paths).read_building_interior_transitions(
            "set-1", "probe-hut-0-0", registry=registry)
        self.assertEqual(restored.interior_transitions.transitions, [building.transitions[1]])

    async def test_sql_failure_rolls_back_and_retry_publishes(self):
        await self.db.conn.execute("CREATE TRIGGER fail_transition BEFORE INSERT ON transitions "
                                   "BEGIN SELECT RAISE(ABORT,'fail'); END")
        await self.db.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.job.materialize_district(self.ctx)
        self.assertEqual(await self.counts(), (0, 0))
        self.assertIsNone(await self.nodes.get_by_id("entry-node"))
        self.assertEqual(await self.locations.get_children("set-1"), [])
        self.assertFalse(self.paths.settlement_structure_path("set-1").exists())
        self.invalidate.assert_not_called()
        await self.db.conn.execute("DROP TRIGGER fail_transition")
        await self.db.conn.commit()
        await self.job.materialize_district(self.ctx)
        self.assertTrue(self.paths.settlement_structure_path("set-1").exists())
        self.assertEqual(await self.counts(), (1, 2))

    async def test_topology_without_transitions_remains_valid(self):
        topology = extract_topology(self.settlement, SettlementTopologyPlan([self.ctx.slot], [], [], []))
        self.assertEqual(topology.sql_transitions, [])
        await self.persist.persist_topology(topology)
        await self.persist.persist_topology(topology)
        self.assertEqual(await self.counts(), (0, 0))
