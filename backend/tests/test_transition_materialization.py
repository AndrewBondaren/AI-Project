"""A1 generation → extraction → SQL/pack → unified read/CRUD acceptance."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.container import Container
from app.db.database import Database
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation
from app.db.models.locationLevel import LocationLevel
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import StructureAreaAssembler
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import extract_settlement
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import SettlementOutdoorSqlPersist
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.transitions.transitionReadService import BuildingTransitionPackBinding
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.spatial.facing import Facing
from tests.structureWire import room_wire, level_wire
from tests.test_settlement_outdoor_extract import _layout, _settlement


class TransitionMaterializationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "acceptance.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.world = World("w1", "Acceptance", "2026-10-06")
        self.settlement = _settlement()
        await self.container.world_repository().create(self.world)
        await self.container.location_repository().create(self.settlement)
        structure = StructureTemplate(
            system_name="00000000-0000-4000-8000-000000000011", display_name="Acceptance", default_z_height=6,
            levels=[level_wire(rooms=[room_wire(size={"width_range": [18, 18], "depth_range": [18, 18]},
                entry_point={"wall": "south", "passage_type": "main_entrance"},
                back_entry_point={"wall": "west", "passage_type": "service_entrance"})]),
                level_wire(z_offset=1, rooms=[room_wire(room_id="upper",
                    size={"width_range": [18, 18], "depth_range": [18, 18]})])],
            staircases=[{"staircase_id": "stairs", "staircase_type": "u_shape", "stops": ["hall", "upper"],
                "size": {"width_range": [5, 5], "depth_range": [5, 5]}, "has_walls": True,
                "in_a_room": True, "embed_in": "hall", "embed_at": "north_east"}])
        self.plot = PlotLayoutTemplate(system_name="acceptance-plot", display_name="Plot",
            occupied_footprint={"min_x": 0, "min_y": 0, "width": 18, "depth": 18},
            main_building={"structure": structure.system_name, "foundation_type": "none", "roof_type": "none"},
            perimeter_barrier={"template": "stone_fence", "probability": 1.0})
        self.catalog = StructureCatalog([structure])
        await self.db.conn.execute("INSERT INTO building_templates(template_uid,system_name,display_name,structure_type,data) "
            "VALUES ('acceptance-plot','acceptance-plot','Plot','building','{}')")
        await self.db.conn.commit()
        self.extracted = extract_settlement(self.settlement, self.generate())
        self.context = self.extracted.transition_context
        self.persist = SettlementOutdoorSqlPersist(self.db, self.container.location_repository(),
            self.container.location_level_repository(), lambda context: SqliteTransitionRepository(self.db, context),
            self.container.connection_persist_service())
        self.paths = WorldPackPaths(Path(self.tmp.name) / "pack", "w1")
        self.writer = WorldPackWriter(self.paths)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def generate(self):
        area = StructureAreaAssembler().assemble(self.world,
            AreaSlot([(x, y) for x in range(30, 70) for y in range(-50, -10)], 7, Facing.SOUTH),
            self.plot, SettlementSkeleton(),
            structure_catalog=self.catalog, building_x=34, building_y=-46)
        layout = _layout(passages=[])
        layout.district_layouts[0].area_layouts = [area]
        layout.district_layouts[0].slot.origin_x = 30
        layout.district_layouts[0].slot.origin_y = -50
        layout.district_layouts[0].slot.ground_z = 7
        return layout

    async def publish(self):
        receipt = self.writer.encode_settlement_structure_tmp("set-1", self.extracted.wire, registry=self.context.registry)
        await self.persist.persist(self.extracted)
        self.writer.publish_settlement_structure(receipt,
            territory_volume={"x0": 0, "y0": -100, "z0": 0, "x1": 100, "y1": 100, "z1": 30},
            packed_district_uids=[self.extracted.districts[0].location_uid], structure_status="complete")
        binding = BuildingTransitionPackBinding("set-1", self.extracted.buildings[0].location_uid,
            frozenset(self.context.levels), frozenset([self.extracted.buildings[0].location_uid]))
        with patch.object(self.container, "world_pack_paths_for", return_value=self.paths):
            return self.container.transition_read_service(self.world, levels=self.context.levels,
                locations=self.context.locations, nodes=self.context.nodes, bindings=[binding])

    async def test_generation_sql_pack_read_repeat_and_crud(self):
        repeated = extract_settlement(self.settlement, self.generate())
        self.assertEqual(repeated.sql_transitions, self.extracted.sql_transitions)
        self.assertEqual(repeated.pack_by_building, self.extracted.pack_by_building)
        self.assertEqual({item.system_transition_type for item in self.extracted.sql_transitions},
            {TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE, TransitionType.GATE})
        self.assertEqual({level.z for level in self.extracted.levels}, {7, 13})
        service = await self.publish()
        building = self.extracted.buildings[0]
        packed = WorldPackReader(self.paths).read_building_interior_transitions("set-1", building.location_uid,
            registry=self.context.registry).interior_transitions.transitions
        self.assertTrue(any(item.system_transition_type == TransitionType.STAIRCASE for item in packed))
        for item in [*packed, *self.extracted.sql_transitions]:
            self.assertEqual(item.transition_uid, transition_uid("w1", item.system_transition_type, item.source, item.destination))
            if item.destination.geometry is not None:
                self.assertGreater(item.destination.x, 0)
                self.assertLess(item.destination.y, 0)
        entries = await service.entries_of("w1", building.location_uid)
        self.assertEqual({item.system_transition_type for item in entries}, {TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE})
        main = next(item for item in entries if item.system_transition_type == TransitionType.MAIN_ENTRANCE)
        repo = SqliteTransitionRepository(self.db, self.context)
        before_parent = building.parent_location_uid
        changed = await repo.update(main.transition_uid,
            {"destination_side": {"is_discovered": False, "is_accessible": False, "entry_difficulty_override": 0}})
        await self.persist.persist(repeated)
        self.assertIn(changed, await service.entries_of("w1", building.location_uid))
        stored_building = await self.container.location_repository().get_by_id(building.location_uid)
        self.assertEqual(stored_building.parent_location_uid, before_parent)
        for level in self.extracted.levels:
            expected = {item.transition_uid for item in [*packed, *self.extracted.sql_transitions]
                        if item.source.level_uid == level.level_uid or item.destination.level_uid == level.level_uid}
            self.assertEqual({item.transition_uid for item in await service.for_level("w1", level.level_uid)}, expected)
        async with self.db.conn.execute("SELECT (SELECT count(*) FROM transitions), (SELECT count(*) FROM transition_sides)") as cursor:
            self.assertEqual(tuple(await cursor.fetchone()), (len(self.extracted.sql_transitions), 2 * len(self.extracted.sql_transitions)))
        async with self.db.conn.execute("PRAGMA foreign_key_check") as cursor:
            self.assertEqual(await cursor.fetchall(), [])

    async def test_runtime_symbolic_and_concrete_cross_branch_crud(self):
        await self.publish()
        other = NamedLocation("other", "w1", "Other branch", "building", "2026-10-06")
        level = LocationLevel("other-level", "other", 7, 6, "Other")
        await self.container.location_repository().create(other)
        await self.container.location_level_repository().upsert_bulk([level])
        context = TransitionRepositoryContext("w1", self.context.registry,
            {**self.context.levels, level.level_uid: level}, {**self.context.locations, other.location_uid: other}, self.context.nodes)
        repo = SqliteTransitionRepository(self.db, context)
        primary = next(item for item in self.extracted.sql_transitions if item.system_transition_type == TransitionType.MAIN_ENTRANCE)
        destination = TransitionEndpoint(space="level", level_uid=level.level_uid, host_location_uid=other.location_uid, x=200, y=-300, z=7)
        for source in (TransitionEndpoint(), primary.destination):
            item = Transition(transition_uid=transition_uid("w1", TransitionType.DOOR, source, destination),
                world_uid="w1", system_transition_type=TransitionType.DOOR, origin=TransitionOrigin.RUNTIME,
                source=source, destination=destination, destination_side=TransitionSide(owner_location_uid=other.location_uid))
            self.assertEqual(await repo.create(item), item)
            self.assertIn(item, await repo.touching_level("w1", level.level_uid))
            changed = await repo.update(item.transition_uid, {"is_active": False})
            self.assertFalse(changed.is_active)
            self.assertTrue(await repo.delete(item.transition_uid))
            self.assertIsNone(await repo.get(item.transition_uid))
        self.assertIsNone((await self.container.location_repository().get_by_id("other")).parent_location_uid)
