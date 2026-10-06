"""P2: real SQLite aggregate CRUD, caller transactions, bulk rollback and hydration."""

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.bulkSql import executemany_rows
from app.db.database import Database
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository


class TransitionRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "repository.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        await self.db.conn.execute("INSERT INTO worlds(world_uid, name, created_at) VALUES ('world', 'W', '2026-10-06')")
        await self.db.conn.execute(
            "INSERT INTO named_locations(location_uid, world_uid, system_location_type, display_name, created_at) "
            "VALUES ('house', 'world', 'building', 'House', '2026-10-06')")
        await self.db.conn.execute(
            "INSERT INTO location_levels(level_uid, location_uid, z, display_name) VALUES ('floor', 'house', 28, 'Floor')")
        await self.db.conn.execute(
            "INSERT INTO connection_nodes(node_uid, world_uid, x, y, z, node_type, graph_level) "
            "VALUES ('node', 'world', 1, 2, 28, 'building_entrance', 'area')")
        await self.db.conn.commit()
        self.context = TransitionRepositoryContext(
            world_uid="world", registry=WorldTransitionTypeRegistry.canonical_engine(),
            levels={"floor": LocationLevel("floor", "house", 28, 3, "Floor")},
            locations={"house": NamedLocation("house", "world", "House", "building", "2026-10-06")},
            nodes={"node": ConnectionNode("node", 1, 2, 28, "building_entrance", "area", "world")},
        )
        self.repo = SqliteTransitionRepository(self.db, self.context)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def transition(self, uid="t", **wire):
        return Transition.model_validate({
            "transition_uid": uid, "world_uid": "world", "system_transition_type": "main_entrance",
            "source": {"x": 1, "y": 2, "z": 28, "node_uid": "node"},
            "destination": {"space": "level", "level_uid": "floor", "x": 2, "y": 2, "z": 28},
            "destination_side": {"owner_location_uid": "house"},
            **wire,
        }, context={"transition_type_registry": self.context.registry})

    async def counts(self):
        async with self.db.conn.execute(
            "SELECT (SELECT count(*) FROM transitions), (SELECT count(*) FROM transition_sides)") as cursor:
            return tuple(await cursor.fetchone())

    async def fail_destination(self, operation="INSERT"):
        await self.db.conn.execute(
            f"CREATE TRIGGER fail_destination BEFORE {operation} ON transition_sides "
            "WHEN NEW.side='destination' BEGIN SELECT RAISE(ABORT, 'destination failure'); END")
        await self.db.conn.commit()

    async def test_create_get_missing_and_duplicate_create(self):
        aggregate = self.transition()
        self.assertIsNone(await self.repo.get("missing"))
        self.assertEqual(await self.repo.create(aggregate), aggregate)
        self.assertEqual(await self.repo.get("t"), aggregate)
        self.assertEqual(await self.counts(), (1, 2))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.create(aggregate)
        self.assertEqual(await self.counts(), (1, 2))

    async def test_update_merges_endpoint_and_side_patches_without_defaults_reset(self):
        original = self.transition(destination_side={"owner_location_uid": "house", "is_discovered": False})
        await self.repo.create(original)
        updated = await self.repo.update("t", {
            "display_name": "New", "destination": {"x": 3},
            "destination_side": {"guard_level_override": 0, "is_accessible": False},
        })
        self.assertEqual(updated.destination.x, 3)
        self.assertEqual(updated.destination.level_uid, "floor")
        self.assertFalse(updated.destination_side.is_discovered)
        self.assertFalse(updated.destination_side.is_accessible)
        self.assertEqual(updated.destination_side.guard_level_override, 0)
        self.assertEqual(updated.destination_side.owner_location_uid, "house")
        self.assertEqual(await self.repo.get("t"), updated)

    async def test_invalid_full_update_and_identity_changes_leave_original(self):
        original = await self.repo.create(self.transition())
        for changes in ({"transition_uid": "other"}, {"world_uid": "other"},
                        {"destination_side": {"entry_difficulty_override": 101}},
                        {"destination": {"level_uid": "missing"}},
                        {"source": {"x": 4}}, {"is_bidirectional": False}, {"unknown": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                await self.repo.update("t", changes)
            self.assertEqual(await self.repo.get("t"), original)
        with self.assertRaises(KeyError):
            await self.repo.update("missing", {"display_name": "New"})

    async def test_create_second_side_failure_rolls_back_whole_aggregate(self):
        await self.fail_destination()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.create(self.transition())
        self.assertEqual(await self.counts(), (0, 0))

    async def test_update_second_side_failure_rolls_back_root_and_first_side(self):
        original = await self.repo.create(self.transition())
        await self.fail_destination("UPDATE")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.update("t", {"display_name": "Changed", "source_side": {"is_accessible": False}})
        self.assertEqual(await self.repo.get("t"), original)

    async def test_savepoint_rolls_back_failed_create_when_caller_catches_error(self):
        await self.fail_destination()
        async with self.db.transaction():
            await self.db.conn.execute("UPDATE worlds SET name='Caller change' WHERE world_uid='world'")
            with self.assertRaises(sqlite3.IntegrityError):
                await self.repo.create(self.transition())
        self.assertEqual(await self.counts(), (0, 0))
        async with self.db.conn.execute("SELECT name FROM worlds WHERE world_uid='world'") as cursor:
            self.assertEqual((await cursor.fetchone())[0], "Caller change")

    async def test_successful_create_remains_in_caller_transaction(self):
        with self.assertRaisesRegex(RuntimeError, "caller rollback"):
            async with self.db.transaction():
                await self.repo.create(self.transition())
                raise RuntimeError("caller rollback")
        self.assertEqual(await self.counts(), (0, 0))

    async def test_bulk_is_idempotent_uses_shared_helper_and_updates_without_replace(self):
        aggregates = [self.transition("one"), self.transition("two")]
        with patch("app.db.repositories.sqlite.transitionRepository.executemany_rows", wraps=executemany_rows) as bulk:
            self.assertEqual(await self.repo.upsert_bulk(aggregates), 2)
            self.assertEqual(bulk.call_count, 2)
        self.assertEqual(await self.repo.upsert_bulk(aggregates), 2)
        self.assertEqual(await self.counts(), (2, 4))
        await self.db.conn.execute("CREATE TABLE transition_ref(uid TEXT REFERENCES transitions(transition_uid) ON DELETE RESTRICT)")
        await self.db.conn.execute("INSERT INTO transition_ref VALUES ('one')")
        await self.db.conn.commit()
        changed = aggregates[0].model_copy(update={"display_name": "Changed"})
        await self.repo.upsert_bulk([changed])
        self.assertEqual((await self.repo.get("one")).display_name, "Changed")
        await self.repo.update("one", {"display_name": "Changed again"})
        self.assertEqual((await self.repo.get("one")).display_name, "Changed again")

    async def test_bulk_sql_failure_rolls_back_every_root_and_side(self):
        await self.fail_destination()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.upsert_bulk([self.transition("one"), self.transition("two")])
        self.assertEqual(await self.counts(), (0, 0))
        self.assertEqual(await self.repo.upsert_bulk([]), 0)

    async def test_bulk_does_not_reassign_uid_from_another_world(self):
        original = await self.repo.create(self.transition())
        await self.db.conn.execute("INSERT INTO worlds(world_uid, name, created_at) VALUES ('other', 'Other', '2026-10-06')")
        await self.db.conn.commit()
        other_context = replace(self.context, world_uid="other", levels={}, locations={}, nodes={})
        other = SqliteTransitionRepository(self.db, other_context)
        collision = Transition(
            transition_uid="t", world_uid="other", system_transition_type="door",
            source={}, destination={},
        )
        with self.assertRaisesRegex(ValueError, "another world"):
            await other.upsert_bulk([collision])
        self.assertEqual(await self.repo.get("t"), original)
        self.assertIsNone(await other.get("t"))
        self.assertEqual(await self.counts(), (1, 2))

    async def test_fk_failure_after_validation_rolls_back_aggregate(self):
        # Caller snapshot may be stale; SQLite FK remains the last consistency gate.
        ghost = replace(self.context.locations["house"], location_uid="ghost")
        repo = SqliteTransitionRepository(self.db, replace(self.context, locations={"house": self.context.locations["house"], "ghost": ghost}))
        transition = self.transition(destination_side={"owner_location_uid": "ghost"})
        with self.assertRaises(sqlite3.IntegrityError):
            await repo.create(transition)
        self.assertEqual(await self.counts(), (0, 0))

    async def test_delete_missing_cascade_and_restrict_preserves_aggregate(self):
        self.assertFalse(await self.repo.delete("missing"))
        original = await self.repo.create(self.transition())
        await self.db.conn.execute("CREATE TABLE transition_ref(uid TEXT REFERENCES transitions(transition_uid) ON DELETE RESTRICT)")
        await self.db.conn.execute("INSERT INTO transition_ref VALUES ('t')")
        await self.db.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.delete("t")
        self.assertEqual(await self.repo.get("t"), original)
        await self.db.conn.execute("DELETE FROM transition_ref")
        await self.db.conn.commit()
        self.assertTrue(await self.repo.delete("t"))
        self.assertEqual(await self.counts(), (0, 0))

    async def test_queries_return_aggregates_and_do_not_filter_entry_type(self):
        main, door = self.transition("main"), self.transition("door", system_transition_type="door")
        source_owned = self.transition("source-only", source_side={"owner_location_uid": "house"}, destination_side={})
        await self.repo.upsert_bulk([main, door, source_owned])
        self.assertEqual({t.transition_uid for t in await self.repo.owned_by_destination("world", "house")}, {"main", "door"})
        self.assertEqual(len(await self.repo.touching_level("world", "floor")), 3)
        self.assertEqual(len(await self.repo.touching_node("world", "node")), 3)
        self.assertEqual(await self.repo.touching_node("world", "missing"), [])
        with self.assertRaises(ValueError):
            await self.repo.touching_level("other", "floor")

    async def test_custom_registry_hydration_has_no_hidden_world_reads(self):
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "royal_entry", "display_name": "Вход", "behaves_as": "main_entrance"},
        ])
        self.context = replace(self.context, registry=registry)
        repo = SqliteTransitionRepository(self.db, self.context)
        transition = self.transition(system_transition_type="royal_entry")
        self.assertEqual(await repo.create(transition), transition)
        self.assertEqual(await repo.get("t"), transition)

    async def test_get_detects_incomplete_aggregate(self):
        await self.repo.create(self.transition())
        await self.db.conn.execute("DELETE FROM transition_sides WHERE side='destination'")
        await self.db.conn.commit()
        with self.assertRaisesRegex(ValueError, "exactly two sides"):
            await self.repo.get("t")


if __name__ == "__main__":
    unittest.main()
