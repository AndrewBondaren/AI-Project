"""G5 actual barrier openings, graph path binding, collector and SQL/pack."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import AreaThresholdKind
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import StructureAreaAssembler
from app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers import area_gate_cells, should_build_area_barrier
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import extract_settlement
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import SettlementOutdoorSqlPersist
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.core.container import Container
from app.db.database import Database
from app.db.models.world import World
from app.db.models.mapCell import MapCell
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.spatial.facing import Facing, CARDINAL_FACINGS, GRID_OUTWARD_DELTA
from tests.test_settlement_outdoor_extract import _layout, _settlement
from tests.test_structure_area_assembler import StructureAreaAssemblerTests


class AreaGatesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World("w1", "Area", "2026-10-06")
        self.plot = PlotLayoutTemplate(system_name="yard", display_name="Yard",
            perimeter_barrier={"template": "stone_fence", "probability": 1.0})
        self.skeleton = SettlementSkeleton()
        self.assembler = StructureAreaAssembler()

    def assemble(self, *, plot=None, facing=Facing.SOUTH, x=20, catalog=None, building_x=None, building_y=None):
        slot = AreaSlot([(xx, yy) for xx in range(x, x + 9) for yy in range(30, 39)], 7, facing)
        return self.assembler.assemble(self.world, slot, self.plot if plot is None else plot,
            self.skeleton, structure_catalog=catalog or StructureCatalog.empty(),
            building_x=building_x, building_y=building_y)

    async def test_facing_geometry_without_building_or_area_nl(self):
        for facing in CARDINAL_FACINGS:
            with self.subTest(facing=facing):
                area = self.assemble(facing=facing)
                self.assertIsNone(area.building_location)
                gate = area_gate_cells(area.barrier_cells)[0]
                self.assertEqual(area.threshold.kind, AreaThresholdKind.GATE)
                self.assertEqual(area.threshold.cells, [(gate.x, gate.y)])
                self.assertEqual(area.threshold.z, gate.z)
                self.assertEqual(len(area.transitions), 1)
                item = area.transitions[0]
                self.assertEqual(item.system_transition_type, TransitionType.GATE)
                dx, dy = GRID_OUTWARD_DELTA[facing]
                self.assertEqual(item.source.geometry, (gate.x + dx, gate.y + dy, gate.z))
                self.assertEqual(item.destination.geometry, (gate.x - dx, gate.y - dy, gate.z))
                self.assertEqual(item.type_params.width_cells, 1)
                self.assertIsNone(item.source.host_location_uid)
                self.assertIsNone(item.destination_side.owner_location_uid)
                self.assertEqual(item.transition_uid, transition_uid("w1", TransitionType.GATE, item.source, item.destination))
                threshold_node = next(node for node in area.connection_nodes if (node.x, node.y, node.z) == (gate.x, gate.y, gate.z))
                self.assertTrue(any(edge.to_node_uid == threshold_node.node_uid for edge in area.connection_edges))

    async def test_open_missing_and_probability_barriers_follow_actual_cells(self):
        for barrier in ({"probability": 0.0}, {"template": "unknown", "probability": 1.0}):
            area = self.assemble(plot=self.plot.model_copy(update={"perimeter_barrier":
                type(self.plot.perimeter_barrier)(**barrier)}))
            self.assertEqual(area.barrier_cells, [])
            self.assertEqual(area.transitions, [])
            self.assertEqual(area.threshold.kind, AreaThresholdKind.PARCEL_EDGE)
        plot = self.plot.model_copy(update={"perimeter_barrier":
            self.plot.perimeter_barrier.model_copy(update={"probability": 0.5})})
        outcomes = set()
        for x in range(20, 30):
            with patch("app.application.worldData.generators.assemblers.areaAssembler.planner.areaBarriers.should_build_area_barrier",
                       wraps=should_build_area_barrier) as decision:
                area = self.assemble(plot=plot, x=x)
                self.assertEqual(decision.call_count, 1)
                self.assertEqual(bool(area.transitions), bool(area.barrier_cells))
                self.assertEqual(area.threshold.kind == AreaThresholdKind.GATE, bool(area.barrier_cells))
                outcomes.add(bool(area.barrier_cells))
        self.assertEqual(outcomes, {False, True})

    async def test_yard_path_goes_through_gate_and_door_stays_separate(self):
        fixture = StructureAreaAssemblerTests()
        fixture.setUp()
        plot = fixture.plot.model_copy(update={"perimeter_barrier": self.plot.perimeter_barrier})
        area = self.assemble(plot=plot, catalog=fixture.catalog, building_x=22, building_y=32)
        self.assertEqual(len(area.transitions), 1)
        gate = area_gate_cells(area.barrier_cells)[0]
        node = next(node for node in area.connection_nodes if (node.x, node.y) == (gate.x, gate.y))
        self.assertTrue(any(edge.to_node_uid == node.node_uid for edge in area.connection_edges))
        self.assertTrue(any(edge.from_node_uid == node.node_uid for edge in area.connection_edges))
        self.assertTrue(any(item.system_transition_type == TransitionType.MAIN_ENTRANCE
                            for item in area.building_layout.transitions))
        self.assertNotIn(area.transitions[0], area.building_layout.transitions)

    async def test_buildingless_gate_follows_final_approach_clamp(self):
        area = self.assemble()
        gate = area_gate_cells(area.barrier_cells)[0]
        street = (gate.x, gate.y - 1)
        terrain = [MapCell("w1", x, y, 7) for x, y in area.slot.cells]
        terrain.append(MapCell("w1", *street, 0))
        area = self.assembler.assemble(self.world, area.slot, self.plot, self.skeleton, terrain,
            structure_catalog=StructureCatalog.empty(), street_xy={street})
        gate = area_gate_cells(area.barrier_cells)[0]
        self.assertLess(area.threshold.z, 7)
        self.assertEqual(gate.z, area.threshold.z)
        self.assertEqual(area.transitions[0].source.z, gate.z)
        self.assertEqual(area.transitions[0].destination.z, gate.z)
        self.assertTrue(any((node.x, node.y, node.z) == (gate.x, gate.y, gate.z) for node in area.connection_nodes))

    async def test_buildingless_collector_sql_sides_and_pack_without_area_location(self):
        area = self.assemble()
        layout = _layout(passages=[])
        layout.district_layouts[0].area_layouts = [area]
        settlement = _settlement()
        extracted = extract_settlement(settlement, layout)
        self.assertEqual(extracted.sql_transitions, area.transitions)
        self.assertEqual(extracted.buildings, [])
        self.assertEqual(extracted.pack_by_building, {})
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(str(Path(tmp) / "world.sqlite"))
            await db.connect()
            try:
                await db.apply_migrations()
                container = Container(None, db)
                await container.world_repository().create(self.world)
                await container.location_repository().create(settlement)
                persist = SettlementOutdoorSqlPersist(db, container.location_repository(), container.location_level_repository(),
                    lambda context: SqliteTransitionRepository(db, context), container.connection_persist_service())
                paths = WorldPackPaths(Path(tmp) / "pack", "w1")
                writer = WorldPackWriter(paths)
                receipt = writer.encode_settlement_structure_tmp("set-1", extracted.wire, registry=extracted.transition_context.registry)
                await persist.persist(extracted)
                repo = SqliteTransitionRepository(db, extracted.transition_context)
                changed = await repo.update(area.transitions[0].transition_uid,
                    {"destination_side": {"is_accessible": False}})
                await persist.persist(extracted)
                self.assertEqual(await repo.get(changed.transition_uid), changed)
                async with db.conn.execute("SELECT (SELECT count(*) FROM transitions), (SELECT count(*) FROM transition_sides)") as cursor:
                    self.assertEqual(tuple(await cursor.fetchone()), (1, 2))
                self.assertEqual(len(await container.location_repository().get_by_world("w1")), 2)
                writer.publish_settlement_structure(receipt,
                    territory_volume={"x0": 0, "y0": 0, "z0": 0, "x1": 100, "y1": 100, "z1": 20},
                    packed_district_uids=[extracted.districts[0].location_uid], structure_status="complete")
                restored = WorldPackReader(paths).read_settlement_structure("set-1", registry=extracted.transition_context.registry)
                self.assertEqual(restored, extracted.wire)
            finally:
                await db.disconnect()
