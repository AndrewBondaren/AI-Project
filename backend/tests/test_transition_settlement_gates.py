"""C23 gate aggregates preserve the road graph and reach the production writer."""
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from app.core.container import Container
from app.db.database import Database
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import SettlementGeneratorService
from app.application.worldData.generators.assemblers.settlementAssembler.planner.topologyPlan import plan_city_graph_for_slots
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import extract_topology
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import SettlementOutdoorSqlPersist
from app.application.worldData.settlementOutdoor.settlementOutdoorTopologyJob import SettlementOutdoorTopologyJob
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.locations.transitions.transitionType import TransitionType
from tests.test_settlement_topology import _world, _settlement, _skeleton


class SettlementGatesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "world.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.world = _world()
        self.settlement = replace(_settlement(), map_x=3, map_y=-2, map_z=7)
        await self.container.world_repository().create(self.world)
        await self.container.location_repository().create(self.settlement)
        self.generator = SettlementGeneratorService()
        self.topology = self.generator.plan_slots_and_city_graph(self.world, self.settlement)
        self.persist = SettlementOutdoorSqlPersist(self.db, self.container.location_repository(),
            self.container.location_level_repository(), lambda context: SqliteTransitionRepository(self.db, context),
            self.container.connection_persist_service())

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    async def test_gate_anchors_uid_and_graph_are_stable_without_parent(self):
        self.assertIsNone(self.settlement.parent_location_uid)
        self.assertTrue(self.topology.transitions)
        nodes, edges = plan_city_graph_for_slots(self.world, self.settlement,
            _skeleton(self.world, self.settlement), self.topology.slots, None)
        self.assertEqual((self.topology.nodes, self.topology.edges), (nodes, edges))
        repeated = self.generator.plan_slots_and_city_graph(self.world, self.settlement)
        self.assertEqual(repeated, self.topology)
        gates = {node.node_uid: node for node in nodes if node.node_type == ConnectionNodeType.SETTLEMENT_GATE.value}
        self.assertEqual(len(self.topology.transitions), len(gates))
        for item in self.topology.transitions:
            node = gates[item.destination.node_uid]
            self.assertEqual(item.destination.geometry, (node.x, node.y, node.z))
            self.assertEqual(item.destination.z, 7)
            self.assertIsNone(item.source.geometry)
            self.assertIsNone(item.source.host_location_uid)
            self.assertEqual(item.destination.host_location_uid, self.settlement.location_uid)
            self.assertEqual(item.destination_side.owner_location_uid, self.settlement.location_uid)
            self.assertEqual(item.system_transition_type, TransitionType.MAIN_ENTRANCE)
            self.assertEqual(item.transition_uid, transition_uid(item.world_uid,
                item.system_transition_type, item.source, item.destination))

    async def test_no_settlement_gate_nodes_produces_no_transitions(self):
        settlement = replace(self.settlement, location_payload={**(self.settlement.location_payload or {}), 'perimeter_barrier': None})
        topology = self.generator.plan_slots_and_city_graph(self.world, settlement)
        self.assertFalse(any(node.node_type == ConnectionNodeType.SETTLEMENT_GATE.value for node in topology.nodes))
        self.assertEqual(topology.transitions, [])
        self.assertEqual(extract_topology(settlement, topology).sql_transitions, [])

    async def test_production_topology_job_persists_nodes_then_two_sides_and_skips_repeat(self):
        job = SettlementOutdoorTopologyJob(self.container.location_repository(), self.persist,
            self.generator, self.container.connection_node_repository())
        facade = Mock(get_footprint_terrain=AsyncMock(return_value=[]))
        result, _ = await job.plan_one(self.world, self.settlement, facade)
        self.assertEqual(result.status, "planned")
        self.assertEqual(result.gates, len(self.topology.transitions))
        extracted = extract_topology(self.settlement, self.topology)
        repo = SqliteTransitionRepository(self.db, extracted.transition_context)
        for item in self.topology.transitions:
            self.assertEqual(await repo.get(item.transition_uid), item)
        async with self.db.conn.execute("SELECT count(*) FROM transition_sides") as cursor:
            self.assertEqual((await cursor.fetchone())[0], 2 * result.gates)
        again, _ = await job.plan_one(self.world, self.settlement, facade)
        self.assertEqual(again.status, "skipped")
        self.assertEqual(facade.get_footprint_terrain.await_count, 1)

    async def test_service_type_and_state_survive_extract_and_repeat_write(self):
        main = self.topology.transitions[0]
        service = main.model_copy(update={"system_transition_type": TransitionType.SERVICE_ENTRANCE,
            "transition_uid": transition_uid(main.world_uid, TransitionType.SERVICE_ENTRANCE, main.source, main.destination)})
        topology = replace(self.topology, transitions=[service, *self.topology.transitions[1:]])
        extracted = extract_topology(self.settlement, topology)
        await self.persist.persist_topology(extracted)
        repo = SqliteTransitionRepository(self.db, extracted.transition_context)
        changed = await repo.update(service.transition_uid,
            {"destination_side": {"is_accessible": False, "entry_difficulty_override": 0}})
        await self.persist.persist_topology(extracted)
        self.assertEqual(await repo.get(service.transition_uid), changed)

    async def test_wrong_node_geometry_rejected_before_sql_and_sql_failure_rolls_back(self):
        item = self.topology.transitions[0]
        wrong = item.model_copy(update={"destination": item.destination.model_copy(update={"z": 8})})
        with self.assertRaisesRegex(ValueError, "matching concrete endpoint geometry"):
            extract_topology(self.settlement, replace(self.topology, transitions=[wrong]))
        await self.db.conn.execute("CREATE TRIGGER fail_transition BEFORE INSERT ON transitions "
            "BEGIN SELECT RAISE(ABORT,'fail'); END")
        await self.db.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.persist.persist_topology(extract_topology(self.settlement, self.topology))
        self.assertEqual(await self.container.connection_node_repository().get_by_world(self.world.world_uid), [])
        self.assertEqual(await self.container.location_repository().get_children(self.settlement.location_uid), [])
