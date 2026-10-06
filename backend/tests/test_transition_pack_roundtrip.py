"""K2 explicit G1→G2→tmp→SQL commit→publish→fresh reader integration."""

import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.application.worldData.connectionPersistService import ConnectionPersistService
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.io.packBlobWire import InteriorTransitionsRebuildRequired
from app.application.worldData.pack.read.settlementStructureIndex import transitions_for_level
from app.application.worldData.settlementOutdoor.settlementOutdoorTransitions import project_settlement_transitions
from app.application.worldData.settlementOutdoor.settlementOutdoorShell import cells_to_shell_wires
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.application.worldData.transitions.transitionStoragePolicy import BuildingTransitionScope
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.dataModel.worldPack.settlementStructureWire import SettlementStructureWire
from app.db.database import Database
from app.db.models.connectionNode import ConnectionNode
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.db.repositories.sqlite.namedLocationRepository import SqliteNamedLocationRepository
from app.db.repositories.sqlite.locationLevelRepository import SqliteLocationLevelRepository
from app.db.repositories.sqlite.connectionNodeRepository import SqliteConnectionNodeRepository
from app.db.repositories.sqlite.connectionEdgeRepository import SqliteConnectionEdgeRepository
from app.db.repositories.sqlite.connectionEdgeCellRepository import SqliteConnectionEdgeCellRepository
from tests.test_structure_orientation import simple_structure, test_world_building


class TransitionPackRoundtripTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world, self.building = test_world_building()
        self.paths = WorldPackPaths(Path(self.tmp.name) / "pack", self.world.world_uid)
        self.writer = WorldPackWriter(self.paths)
        self.db = Database(str(Path(self.tmp.name) / "world.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        await self.db.conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES (?,?,?)",
                                   (self.world.world_uid, self.world.name, self.world.created_at))
        await self.db.conn.commit()
        template = simple_structure()
        neighbor = deepcopy(template.levels[0]["rooms"][0])
        neighbor.update(room_id="kitchen", display_name="Kitchen")
        neighbor.pop("entry_point")
        template.levels[0]["rooms"].append(neighbor)
        template.connections.append({"from_room": "hall", "to_room": "kitchen", "passage_type": "doorway"})
        self.layout = StructureGeneratorService().generate_from_template(self.world, self.building, template)
        self.registry = WorldTransitionTypeRegistry.model_validate([
            *WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
            {"system_type": "custom_doorway", "display_name": "Doorway", "behaves_as": "doorway"},
        ])
        self.transitions = []
        self.nodes = {}
        for item in self.layout.transitions:
            wire = item.model_dump(mode="json")
            if item.system_transition_type == TransitionType.DOORWAY:
                wire["system_transition_type"] = "custom_doorway"
                wire["destination_side"].update(is_discovered=False, is_accessible=False, entry_difficulty_override=0)
            if item.system_transition_type == TransitionType.MAIN_ENTRANCE:
                node = ConnectionNode("entry-node", *item.source.geometry, "building_entrance", "area", self.world.world_uid)
                self.nodes[node.node_uid] = node
                wire["source"]["node_uid"] = node.node_uid
            validated = Transition.model_validate(wire, context={"transition_type_registry": self.registry})
            self.transitions.append(validated.model_copy(update={"transition_uid": transition_uid(
                validated.world_uid, validated.system_transition_type, validated.source, validated.destination)}))
        self.context = TransitionRepositoryContext(self.world.world_uid, self.registry,
            {level.level_uid: level for level in self.layout.levels},
            {location.location_uid: location for location in [self.building, *self.layout.rooms]}, self.nodes)
        scope = BuildingTransitionScope(self.building.location_uid, frozenset(self.context.levels),
                                        frozenset(item.transition_uid for item in self.transitions))
        self.projection = project_settlement_transitions(self.world.world_uid, self.transitions,
            levels=self.context.levels, locations=self.context.locations, nodes=self.nodes,
            building_scopes=[scope], registry=self.registry)
        self.repo = SqliteTransitionRepository(self.db, self.context)
        self.wire = self.make_wire()
        self.volume = {"x0": 0, "y0": -50, "z0": 0, "x1": 100, "y1": 100, "z1": 50}

    def make_wire(self, interior=True, district="district", building=None):
        return SettlementStructureWire.model_validate({"settlement_uid": "settlement", "districts": [{
            "location_uid": district, "areas": [{"area_uid": "area", "slot": {"ground_z": 7, "facing": "south"},
                "buildings": [{"location_uid": building or self.building.location_uid,
                    "shell_cells": [cell.model_dump(mode="json") for cell in cells_to_shell_wires(self.layout.cells)],
                    **({"interior_transitions": self.projection.pack_by_building[self.building.location_uid].model_dump(mode="json")}
                       if interior else {}),
                }]}]}]}, context={"transition_type_registry": self.registry})

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    async def persist_sql(self):
        async with self.db.transaction():
            await SqliteNamedLocationRepository(self.db).upsert_bulk(list(self.context.locations.values()))
            await SqliteLocationLevelRepository(self.db).upsert_bulk(self.layout.levels)
            graph = ConnectionPersistService(SqliteConnectionNodeRepository(self.db),
                SqliteConnectionEdgeRepository(self.db), SqliteConnectionEdgeCellRepository(self.db))
            await graph.persist_graph(list(self.nodes.values()), [], [])
            await self.repo.upsert_bulk(self.projection.sql_transitions)

    def publish(self, writer, tmp):
        return writer.publish_settlement_structure(tmp, territory_volume=self.volume,
                                                   packed_district_uids=["district"], structure_status="complete")

    def read_building(self):
        return WorldPackReader(self.paths).read_building_interior_transitions(
            "settlement", self.building.location_uid, registry=self.registry)

    async def test_sql_and_pack_roundtrip_have_exact_aggregate_and_uid_agreement(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        self.assertFalse(self.paths.settlement_structure_path("settlement").exists())
        await self.persist_sql()
        self.publish(self.writer, tmp)
        restored = self.read_building()
        self.assertEqual(restored.interior_transitions, self.projection.pack_by_building[self.building.location_uid])
        self.assertTrue(restored.shell_cells)
        packed = restored.interior_transitions.transitions
        self.assertTrue(packed)
        for item in self.projection.sql_transitions:
            self.assertEqual(await self.repo.get(item.transition_uid), item)
        for item in packed:
            self.assertIsNone(await self.repo.get(item.transition_uid))
            self.assertFalse(item.destination_side.is_accessible)
            self.assertEqual(item.destination_side.entry_difficulty_override, 0)
        self.assertEqual(transitions_for_level(restored, self.layout.levels[0].level_uid), packed)
        self.assertEqual(transitions_for_level(restored, "missing"), [])
        reader = WorldPackReader(self.paths)
        entry = reader.manifest.settlement_structure_entry("settlement")
        self.assertEqual(entry.structure_hash, tmp.content_hash)
        self.assertEqual(entry.packed_district_uids, ["district"])

    async def test_sql_failure_rolls_back_refs_and_never_publishes_tmp(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        await self.db.conn.execute("CREATE TRIGGER fail_transition BEFORE INSERT ON transitions BEGIN SELECT RAISE(ABORT,'fail'); END")
        await self.db.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.persist_sql()
            self.publish(self.writer, tmp)
        self.assertTrue(tmp.tmp_path.exists())
        self.assertFalse(self.paths.settlement_structure_path("settlement").exists())
        self.assertIsNone(self.writer.manifest.settlement_structure_entry("settlement"))
        async with self.db.conn.execute("SELECT (SELECT count(*) FROM named_locations), (SELECT count(*) FROM connection_nodes), (SELECT count(*) FROM transitions)") as cursor:
            self.assertEqual(tuple(await cursor.fetchone()), (0, 0, 0))

    async def test_interrupted_publish_reloads_tmp_and_retries_without_generation_or_sql(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        await self.persist_sql()
        with patch("app.application.worldData.pack.io.worldPackWriter.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.publish(self.writer, tmp)
        fresh = WorldPackWriter(self.paths)
        recovered = fresh.load_settlement_structure_tmp("settlement")
        self.assertEqual(recovered.content_hash, tmp.content_hash)
        with patch.object(StructureGeneratorService, "generate_from_template", side_effect=AssertionError("regenerated")), \
             patch.object(self.repo, "upsert_bulk", side_effect=AssertionError("SQL repeated")):
            self.publish(fresh, recovered)
        self.assertEqual(self.read_building().interior_transitions,
                         self.projection.pack_by_building[self.building.location_uid])
        self.assertFalse(recovered.tmp_path.exists())

    async def test_manifest_failure_after_blob_publish_recovers_without_duplicate_frames(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        await self.persist_sql()
        with patch.object(self.writer, "save_manifest", side_effect=OSError("manifest interrupted")):
            with self.assertRaises(OSError):
                self.publish(self.writer, tmp)
        self.assertFalse(tmp.tmp_path.exists())
        # Retain the committed receipt and retry metadata publication against the
        # exact published payload; no synthetic tmp and no duplicated district.
        fresh = WorldPackWriter(self.paths)
        self.publish(fresh, tmp)
        reader = WorldPackReader(self.paths)
        wire = reader.read_settlement_structure("settlement", registry=self.registry)
        self.assertEqual(len(wire.districts), 1)
        self.assertEqual(reader.manifest.settlement_structure_entry("settlement").structure_hash, tmp.content_hash)

    async def test_publish_retry_refuses_a_different_blob(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        await self.persist_sql()
        self.publish(self.writer, tmp)
        self.paths.settlement_structure_path("settlement").write_bytes(b"different payload")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.publish(WorldPackWriter(self.paths), tmp)

    async def test_append_retains_published_interior_and_legacy_building_requires_rebuild(self):
        tmp = self.writer.encode_settlement_structure_tmp("settlement", self.wire, registry=self.registry)
        await self.persist_sql()
        self.publish(self.writer, tmp)
        original = self.paths.settlement_structure_path("settlement").read_bytes()
        next_tmp = self.writer.encode_settlement_structure_tmp("settlement",
            self.make_wire(interior=False, district="other", building="legacy"), registry=self.registry)
        self.assertTrue(next_tmp.tmp_path.read_bytes().startswith(original))
        self.writer.publish_settlement_structure(next_tmp, territory_volume=self.volume,
                                                 packed_district_uids=["district", "other"], structure_status="complete")
        reader = WorldPackReader(self.paths)
        self.assertEqual(reader.read_building_interior_transitions("settlement", self.building.location_uid,
            registry=self.registry).interior_transitions, self.projection.pack_by_building[self.building.location_uid])
        with self.assertRaises(InteriorTransitionsRebuildRequired):
            reader.read_building_interior_transitions("settlement", "legacy", registry=self.registry)
